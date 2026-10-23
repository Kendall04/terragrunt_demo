using Amazon.DynamoDBv2;
using Ecs.Backup.Sentinel;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Ingestion;
using Sentinel.Persistence.DynamoDb;
using Sentinel.Worker.Lambda;
namespace Ecs.Backup.Managed;

public static class BackupComposition {
 public static Function Ingestion(BackupSettings settings,IAmazonDynamoDB client,CancellationToken token,Func<DateTimeOffset> clock,IIngestionObserver? observer=null) {
  settings.Validate();
  // All pre-normalization and commit I/O use the same invocation-scoped SDK budget and retention.
  var scoped=new ScopedDynamoClient(client,token);
  var store=new DynamoStore(scoped,settings.Dynamo,settings.Storage);
  var normalizer=new ObserverNormalizer(settings.Subject,settings.Key,store,settings.Policy);
  var processor=new IngestionProcessor(normalizer,new(settings.Account,settings.Region,settings.Project,settings.Environment,[ObserverNormalizer.Producer],[settings.Key]),
   _=>new(new SignalProcessor(store,new IncidentReducer(new BackupIncidentPolicy(settings.Key)),settings.Storage)),_=>settings.Policy,observer,
   at=>new(at,"ecs-backup-observer-v2",[],[]));
  var ingress=new BackupIngress(normalizer,processor);
  MessageResult? Process(string body,string messageId,string invocation,DateTimeOffset received,CancellationToken budget) {
   try {
    budget.ThrowIfCancellationRequested();
    if(normalizer.Read(body,processor.Options,received).Evaluation!="LOCAL_RECEIPT_REPLAY")
     return new(true,FailureClass.Security,"synthetic-replay-only",null);
   } catch(OperationCanceledException) {return new(true,FailureClass.Transient,"cancelled-before-confirmation",null);}
   catch(Exception e) when(e is System.Text.Json.JsonException or InvalidOperationException or ArgumentException or FormatException or KeyNotFoundException or OverflowException) {
    return new(true,FailureClass.Poison,"backup-observer-contract",null);
   }
   return ingress.Process(body,messageId,received,budget,invocation);
  }
  return new Function(processor,Process,clock,settings.QueueArn);
 }
}
