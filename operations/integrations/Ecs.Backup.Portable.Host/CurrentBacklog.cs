using Amazon.DynamoDBv2;
using Amazon.DynamoDBv2.Model;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Operations;
using Sentinel.Persistence.DynamoDb;

namespace Ecs.Backup.Portable.Host;

// Read current authoritative W#/O# rows instead of treating the worker's slow,
// multi-invocation sweep as current telemetry. No journal writes or GSI claims.
// One query + at most 32 reads; with the 13 historical/OP reads, <=46 requests.
public sealed class CurrentBacklog(IAmazonDynamoDB ddb,DynamoOptions options) {
 public int Requests {get;private set;}
 public BacklogObservation Read(DateTimeOffset now) {
  Requests++;
  var page=ddb.QueryAsync(new QueryRequest{TableName=options.Table,ConsistentRead=true,Limit=32,
   KeyConditionExpression="PK = :pk AND begins_with(SK,:w)",
   ExpressionAttributeValues=new(){[":pk"]=PhysicalLayout.S(options.Namespace),[":w"]=PhysicalLayout.S("W#")}}).GetAwaiter().GetResult();
  if(page.Items.Count>32)throw new InvalidDataException("Backlog query exceeded bound.");
  List<OutboxEntry> entries=[];var layout=new PhysicalLayout(options);
  foreach(var row in page.Items) {
   if(row["PK"].S!=options.Namespace||!row["SK"].S.StartsWith("W#",StringComparison.Ordinal))throw new InvalidDataException("Foreign backlog pointer.");
   var id=PhysicalLayout.Payload<string>(row);Requests++;
   var found=ddb.GetItemAsync(new GetItemRequest{TableName=options.Table,Key=layout.Key(PhysicalLayout.Effect(id)),ConsistentRead=true}).GetAwaiter().GetResult();
   if(found.Item is {Count:>0}){var entry=PhysicalLayout.Payload<OutboxEntry>(found.Item);if(entry.Id!=id)throw new InvalidDataException("Backlog identity mismatch.");entries.Add(entry);}
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
