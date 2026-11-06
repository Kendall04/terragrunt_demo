using Amazon.DynamoDBv2;
using Amazon.DynamoDBv2.Model;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Operations;
using Sentinel.Persistence.DynamoDb;

namespace Ecs.Backup.Portable.Host;

// Read current authoritative W#/O# rows instead of treating the worker's slow,
// multi-invocation sweep as current telemetry. No journal writes or GSI claims.
// Worker uses one consistent query + one transaction of at most 32 Get actions.
// Both requests consume its existing 64-request budget, before the checkpoint.
public sealed class CurrentBacklog(IAmazonDynamoDB ddb,DynamoOptions options) {
 public int Requests {get;private set;}
 public BacklogObservation Read(DateTimeOffset now) {
  Requests++;
  var page=ddb.QueryAsync(new QueryRequest{TableName=options.Table,ConsistentRead=true,Limit=32,
   KeyConditionExpression="PK = :pk AND begins_with(SK,:w)",
   ExpressionAttributeValues=new(){[":pk"]=PhysicalLayout.S(options.Namespace),[":w"]=PhysicalLayout.S("W#")}}).GetAwaiter().GetResult();
  if(page.Items.Count>32)throw new InvalidDataException("Backlog query exceeded bound.");
  List<OutboxEntry> entries=[];var layout=new PhysicalLayout(options);
  List<string> ids=[];
  foreach(var row in page.Items) {
   if(row["PK"].S!=options.Namespace||!row["SK"].S.StartsWith("W#",StringComparison.Ordinal))throw new InvalidDataException("Foreign backlog pointer.");
   ids.Add(PhysicalLayout.Payload<string>(row));
  }
  if(ids.Count>0) {
   if(ids.Distinct(StringComparer.Ordinal).Count()!=ids.Count)throw new InvalidDataException("Duplicate work pointer.");
   Requests++;
   var found=ddb.TransactGetItemsAsync(new TransactGetItemsRequest{TransactItems=ids.Select(id=>new TransactGetItem{Get=new Get{TableName=options.Table,Key=layout.Key(PhysicalLayout.Effect(id))}}).ToList()}).GetAwaiter().GetResult();
   if(found.Responses.Count!=ids.Count)throw new InvalidDataException("Incomplete authoritative backlog read.");
   for(int i=0;i<ids.Count;i++)if(found.Responses[i].Item is {Count:>0} item){var entry=PhysicalLayout.Payload<OutboxEntry>(item);if(entry.Id!=ids[i])throw new InvalidDataException("Backlog identity mismatch.");entries.Add(entry);}
  }
  return Observe(entries,now,page.LastEvaluatedKey is not {Count:>0});
 }
 public static BacklogObservation Observe(IEnumerable<OutboxEntry> entries,DateTimeOffset now,bool complete) {
  var result=BacklogObservation.Empty(now,complete);
  foreach(var e in entries) {
   if(e.Status==OutboxStatus.PermanentFailure){result=result with{Failed=result.Failed+1};continue;}
   var due=e.Status is OutboxStatus.Pending or OutboxStatus.Uncertain or OutboxStatus.RetryableFailure
    ?e.DueAt<=now:e.Status==OutboxStatus.Claimed&&e.LeaseUntil<=now;
   if(!due)continue;
   var at=e.Status==OutboxStatus.Claimed?e.LeaseUntil!.Value:e.DueAt;
   DateTimeOffset? Min(DateTimeOffset? old)=>old is null||at<old?at:old;
   var check=e.Intent?.Kind is EffectKind.ScheduleRecoveryCheck or EffectKind.RequestFunctionalProbe;
   var archive=e.Kind==WorkKind.ArchiveDecision;
   result=result with{Checks=result.Checks+(check?1:0),Archives=result.Archives+(archive?1:0),Effects=result.Effects+(!check&&!archive?1:0),
    OldestDueAt=Min(result.OldestDueAt),OldestCheckAt=check?Min(result.OldestCheckAt):result.OldestCheckAt,
    OldestArchiveAt=archive?Min(result.OldestArchiveAt):result.OldestArchiveAt,
    OldestEffectAt=!check&&!archive?Min(result.OldestEffectAt):result.OldestEffectAt};
  }
  return result;
 }
}
