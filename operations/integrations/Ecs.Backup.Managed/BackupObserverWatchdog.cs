using Amazon.DynamoDBv2;
using Amazon.DynamoDBv2.Model;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Observability;
using Sentinel.Persistence.DynamoDb;
namespace Ecs.Backup.Managed;

public sealed record BackupHeartbeat(int SchemaVersion,string RunId,string Subject,DateTimeOffset ObservedAt);

// One monotonic heartbeat item in the existing table/namespace. No status is inferred
// from a heartbeat: an alive observer may report UNKNOWN or a failing backup.
public sealed class BackupHeartbeatStore(IAmazonDynamoDB client,BackupSettings settings) {
 const string Key="CTRL#BACKUP-OBSERVER";
 readonly PhysicalLayout layout=new(settings.Dynamo);
 public BackupHeartbeat? Read(CancellationToken token) {
  var row=client.GetItemAsync(new(){TableName=settings.Dynamo.Table,Key=layout.Key(Key),ConsistentRead=true,ReturnConsumedCapacity=ReturnConsumedCapacity.INDEXES},token).GetAwaiter().GetResult().Item;
  if(row is null || row.Count==0)return null;
  var value=PhysicalLayout.Payload<BackupHeartbeat>(row);
  if(value.SchemaVersion!=1 || value.RunId!=settings.RunId || value.Subject!=settings.Subject || value.ObservedAt.Offset!=TimeSpan.Zero ||
    row.GetValueOrDefault("Observed")?.N!=value.ObservedAt.UtcTicks.ToString(System.Globalization.CultureInfo.InvariantCulture))
   throw new ArgumentException("Heartbeat scope mismatch.");
  return value;
 }
 public bool Touch(DateTimeOffset observed,CancellationToken token) {
  if(observed.Offset!=TimeSpan.Zero)throw new ArgumentException("UTC observation required.");
  var old=Read(token);if(old?.ObservedAt>=observed)return true;
  var next=new BackupHeartbeat(1,settings.RunId,settings.Subject,observed);var item=layout.Item(Key,next);
  item["Observed"]=new(){N=observed.UtcTicks.ToString(System.Globalization.CultureInfo.InvariantCulture)};
  var put=new Put {TableName=settings.Dynamo.Table,Item=item,ConditionExpression=old is null?"attribute_not_exists(#pk)":"#observed = :previous",
   ExpressionAttributeNames=old is null?new(){["#pk"]="PK"}:new(){["#observed"]="Observed"},
   ExpressionAttributeValues=old is null?null:new(){[":previous"]=new(){N=old.ObservedAt.UtcTicks.ToString(System.Globalization.CultureInfo.InvariantCulture)}}};
  try {
   client.TransactWriteItemsAsync(new(){ReturnConsumedCapacity=ReturnConsumedCapacity.INDEXES,ClientRequestToken=DomainJson.StableId("backup-heartbeat-v1",DomainJson.Serialize(next))[..36],TransactItems=[new(){Put=put}]},token).GetAwaiter().GetResult();return true;
  } catch(TransactionCanceledException e) when(e.CancellationReasons?.Any(x=>x.Code=="ConditionalCheckFailed")==true) {return false;}
 }
}

public static class BackupObserverWatchdog {
 public static ProcessingResult? Evaluate(BackupSettings settings,IAmazonDynamoDB client,DateTimeOffset now,CancellationToken token) {
  if(settings.ObserverDeadlineSeconds==0 || !settings.ObserverExpectedUp)return null;
  var heartbeat=new BackupHeartbeatStore(client,settings).Read(token);
  var last=heartbeat?.ObservedAt??settings.StartsAt;
  var service=new ObservedService(settings.Subject,settings.Key,"periodic-backup-observer",settings.Policy,[],[],
   "observer-heartbeat",TimeSpan.FromSeconds(settings.ObserverDeadlineSeconds),[]);
  var signal=TelemetryWatchdog.Evaluate(service,last,now);if(signal is null)return null;
  signal=signal with {Id=DomainJson.StableId(signal.Id,Ecs.Backup.Sentinel.BackupIncidentPolicy.WatchdogProducer),Source=Ecs.Backup.Sentinel.BackupIncidentPolicy.WatchdogProducer};
  var store=new DynamoStore(client,settings.Dynamo,settings.Storage);
  var processor=new SignalProcessor(store,new IncidentReducer(new Ecs.Backup.Sentinel.BackupIncidentPolicy(settings.Key)),settings.Storage);
  token.ThrowIfCancellationRequested();
  var prepared=processor.Prepare(signal,settings.Policy,new(now,BackupSettings.CatalogVersion,[],[]),
   System.Collections.Immutable.ImmutableDictionary<string,string>.Empty.Add("backupStatus","UNKNOWN")
    .Add("backupCode","OBSERVER_HEARTBEAT_EXPIRED").Add("evaluation","OBSERVER_WATCHDOG"));
  var outcome=processor.Confirm(prepared);
  return outcome.Status==ProcessingStatus.Unknown && prepared.Commit is not null?processor.Reconcile(prepared.Commit,now):outcome;
 }
}
