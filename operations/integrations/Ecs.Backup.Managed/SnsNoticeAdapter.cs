using System.Net;
using System.Text.RegularExpressions;
using Amazon.Runtime;
using Amazon.SimpleNotificationService;
using Amazon.SimpleNotificationService.Model;
using Sentinel.Application;
using Sentinel.Core;
namespace Ecs.Backup.Managed;

// SNS Standard offers no producer idempotency token. A known publish ACK is not inbox delivery.
public sealed class SnsNoticeAdapter(IAmazonSimpleNotificationService sns,BackupSettings settings,CancellationToken token) : IEffectAdapter {
 public bool SupportsIdempotency=>false;
 public DeliveryResult Execute(EffectExecution execution) {
  var intent=execution.Entry.Intent;
  if(intent is null || intent.Kind is not (EffectKind.EscalateIncident or EffectKind.ResolveIncident) ||
   execution.Audit is null || execution.Audit.Signal.Key!=settings.Key || execution.IdempotencyKey!=execution.Entry.Id ||
   execution.Audit.Id!=execution.Entry.AuditId || execution.Entry.AggregateKey!=StorageKeys.Aggregate(settings.Key))
   return new(DeliveryStatus.PermanentFailure,"Invalid backup notification identity.");
  // This runtime is a finite sandbox. Only the first episode may publish its alert/recovery pair.
  // The original reducer deduplicates each semantic intent; original durable attempts remain max3.
  if(intent.Epoch!=1)return new(DeliveryStatus.PermanentFailure,"Trial notice limit: later episode preserved without SNS request.");
  if(intent.Kind==EffectKind.ResolveIncident && settings.NotificationMode!="EscalationAndRecovery")
   return new(DeliveryStatus.PermanentFailure,"Recovery notice not enabled by explicit policy.");
  if(token.IsCancellationRequested)return new(DeliveryStatus.RetryableFailure,"Publish not attempted; invocation cancelled.");
  var status=execution.Audit.SourceMetadata?.GetValueOrDefault("backupStatus")??"UNKNOWN";
  if(status is not ("FAILED" or "MISSING" or "STALE" or "UNKNOWN" or "HEALTHY"))return new(DeliveryStatus.PermanentFailure,"Invalid sanitized backup status.");
  var evidence=new BackupNoticeEvidence(1,"Ecs.Backup.Sentinel",settings.SenderLabel,settings.Key.Service,settings.Key.Scope,
   intent.IncidentId,intent.Epoch,execution.Entry.Id,intent.Kind.ToString(),status,"SNS_PUBLISH_ONLY_NOT_INBOX_RECEIPT",settings.Mode=="synthetic-trial");
  var payload=DomainJson.Serialize(evidence);
  var content=BackupNoticeText.Format(evidence,execution.Audit.SourceMetadata?.GetValueOrDefault("backupCode"),execution.Audit.Signal.ObservedAt,settings.Mode=="observer-check");
  try {
   var response=sns.PublishAsync(new PublishRequest {TopicArn=settings.TopicArn,Subject=content.Subject,Message=content.Message,
    MessageAttributes=new(){["BackupEvidence"]=new(){DataType="String",StringValue=payload}}},token).GetAwaiter().GetResult();
   return response.HttpStatusCode==HttpStatusCode.OK && Regex.IsMatch(response.MessageId??"","^[a-zA-Z0-9-]{1,128}$")
    ?new(DeliveryStatus.Confirmed,"SNS accepted message "+response.MessageId+"; inbox delivery unverified.")
    :new(DeliveryStatus.Unknown,"SNS acceptance unproven; preserve same outbox identity.");
  } catch(Exception e) when(e is OperationCanceledException or TimeoutException or IOException) {
   return new(DeliveryStatus.Unknown,"SNS outcome unknown; retry may duplicate delivery.");
  } catch(AmazonServiceException e) when((int)e.StatusCode>=500) {
   return new(DeliveryStatus.Unknown,"SNS service outcome unknown; preserve receipt.");
  } catch(AmazonServiceException e) when((int)e.StatusCode==429 || e.ErrorCode is "Throttled" or "Throttling" or "ThrottlingException") {
   return new(DeliveryStatus.RetryableFailure,"SNS throttled; no provider acceptance confirmed.");
  } catch(AmazonServiceException) {return new(DeliveryStatus.PermanentFailure,"SNS request rejected; no alternate access attempted.");}
  catch(AmazonClientException) {return new(DeliveryStatus.Unknown,"SNS client outcome unknown; preserve receipt without provider details.");}
 }
}
