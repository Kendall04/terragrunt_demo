using Amazon.DynamoDBv2;
using Amazon.DynamoDBv2.Model;
using Sentinel.Core;
using Sentinel.Persistence.DynamoDb;
namespace Ecs.Backup.Managed;

public sealed record BackupCursorRecord(int SchemaVersion,string RunId,long Revision,string? Continuation,string? Worker,DateTimeOffset? LeaseUntil);
public sealed record BackupCursorClaim(BackupCursorRecord Record);

// One control item in the SAME original table/namespace. This is a scheduler checkpoint,
// not an incident store, receipt, outbox or an alternative backend.
public sealed class BackupCursorStore(IAmazonDynamoDB client,BackupSettings settings) {
 const string Key="CTRL#BACKUP-RECONCILE";
 readonly PhysicalLayout layout=new(settings.Dynamo);
 static void Cursor(BackupSettings c,string? value) {
  if(value is null)return;
  if(value.Length>4096)throw new ArgumentException("Bounded checkpoint required.");
  try {
   var fields=System.Text.Json.JsonSerializer.Deserialize<Dictionary<string,string>>(Convert.FromBase64String(value));
   if(fields is null || fields.Count!=2 || fields.GetValueOrDefault("PK")!=c.Dynamo.Namespace ||
      fields.GetValueOrDefault("SK") is not { } sk || !sk.StartsWith("W#",StringComparison.Ordinal))
    throw new ArgumentException("Foreign checkpoint.");
  } catch(Exception e) when(e is FormatException or System.Text.Json.JsonException) {throw new ArgumentException("Invalid checkpoint.");}
 }
 BackupCursorRecord? Read(CancellationToken token) {
  token.ThrowIfCancellationRequested();
  var row=client.GetItemAsync(new GetItemRequest {TableName=settings.Dynamo.Table,Key=layout.Key(Key),ConsistentRead=true,ReturnConsumedCapacity=ReturnConsumedCapacity.INDEXES},token).GetAwaiter().GetResult().Item;
  if(row is null || row.Count==0)return null;
  var record=PhysicalLayout.Payload<BackupCursorRecord>(row);
  if(record.SchemaVersion!=1 || record.RunId!=settings.RunId || record.Revision<1 ||
     row.GetValueOrDefault("Revision")?.N!=record.Revision.ToString(System.Globalization.CultureInfo.InvariantCulture) ||
     (record.Worker is null)!=(record.LeaseUntil is null) || record.LeaseUntil is {Offset.Ticks:not 0})
   throw new ArgumentException("Checkpoint binding mismatch.");
  Cursor(settings,record.Continuation);return record;
 }
 bool Put(BackupCursorRecord next,long? previous,CancellationToken token,BackupCursorRecord? claimed=null) {
  Cursor(settings,next.Continuation);var item=layout.Item(Key,next);
  item["Revision"]=new(){N=next.Revision.ToString(System.Globalization.CultureInfo.InvariantCulture)};
  if(next.Worker is not null)item["Worker"]=new(){S=next.Worker};
  if(next.LeaseUntil is not null)item["Lease"]=new(){N=next.LeaseUntil.Value.UtcTicks.ToString(System.Globalization.CultureInfo.InvariantCulture)};
  var put=new Put {TableName=settings.Dynamo.Table,Item=item,
   ConditionExpression=previous is null?"attribute_not_exists(#pk)":"#revision = :revision",
   ExpressionAttributeNames=previous is null?new(){["#pk"]="PK"}:new(){["#revision"]="Revision"},
   ExpressionAttributeValues=previous is null?null:new(){[":revision"]=new(){N=previous.Value.ToString(System.Globalization.CultureInfo.InvariantCulture)}}};
  if(claimed is not null) {
   if(put.ExpressionAttributeValues is null || claimed.Worker is null || claimed.LeaseUntil is null)throw new ArgumentException("Incomplete cursor claim.");
   put.ConditionExpression+=" AND #worker = :worker AND #lease = :lease";
   put.ExpressionAttributeNames["#worker"]="Worker";put.ExpressionAttributeNames["#lease"]="Lease";
   put.ExpressionAttributeValues[":worker"]=new(){S=claimed.Worker};put.ExpressionAttributeValues[":lease"]=new(){N=claimed.LeaseUntil!.Value.UtcTicks.ToString(System.Globalization.CultureInfo.InvariantCulture)};
  }
  try {
   client.TransactWriteItemsAsync(new(){ReturnConsumedCapacity=ReturnConsumedCapacity.INDEXES,ClientRequestToken=DomainJson.StableId("backup-cursor-v1",DomainJson.Serialize(next))[..36],TransactItems=[new(){Put=put}]},token).GetAwaiter().GetResult();return true;
  } catch(TransactionCanceledException e) when(e.CancellationReasons?.Any(x=>x.Code=="ConditionalCheckFailed")==true) {return false;}
  // Unknown/transport results grant no execution or progress; retain the old page/lease.
 }
 public BackupCursorClaim? Acquire(string worker,DateTimeOffset now,CancellationToken token) {
  settings.Validate();
  if(now.Offset!=TimeSpan.Zero || string.IsNullOrWhiteSpace(worker) || worker.Length>128)throw new ArgumentException("Bounded worker/time required.");
  var old=Read(token);
  if(old?.LeaseUntil>now)return null;
  var next=new BackupCursorRecord(1,settings.RunId,checked((old?.Revision??0)+1),old?.Continuation,worker,now.AddSeconds(30));
  return Put(next,old?.Revision,token)?new(next):null;
 }
 public bool Complete(BackupCursorClaim claim,string? continuation,DateTimeOffset now,CancellationToken token) {
  var record=claim.Record;
  if(record.RunId!=settings.RunId || record.Worker is null || record.LeaseUntil is null || now.Offset!=TimeSpan.Zero)throw new ArgumentException("Foreign checkpoint claim.");
  if(now>=record.LeaseUntil)return false;
  var next=record with {Revision=checked(record.Revision+1),Continuation=continuation,Worker=null,LeaseUntil=null};
  return Put(next,record.Revision,token,record);
 }
}
