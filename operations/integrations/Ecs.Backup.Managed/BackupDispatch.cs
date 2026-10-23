using Amazon.DynamoDBv2;
using Amazon.S3;
using Amazon.S3.Model;
using Amazon.Runtime;
using Amazon.SimpleNotificationService;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Observability;
using Sentinel.Persistence.DynamoDb;
using Sentinel.Persistence.S3;
using Sentinel.Worker.Lambda;
namespace Ecs.Backup.Managed;

public sealed class BackupEffectGate(ITransactionalStore store,BackupSettings settings,IEffectAdapter inner) : IEffectAdapter {
 public bool SupportsIdempotency=>inner.SupportsIdempotency;
 public DeliveryResult Execute(EffectExecution execution) {
  var audit=execution.Audit??store.ReadAudit(execution.Entry.AuditId);
  if(audit is null)return new(DeliveryStatus.RetryableFailure,"Committed backup audit missing.");
  if(execution.Entry.AggregateKey!=StorageKeys.Aggregate(settings.Key) || audit.AggregateKey!=execution.Entry.AggregateKey ||
   audit.Id!=execution.Entry.AuditId || audit.Signal.Key!=settings.Key || audit.Policy.Version!=settings.Policy.Version ||
   DomainJson.Serialize(audit.Policy)!=DomainJson.Serialize(settings.Policy))
   return new(DeliveryStatus.PermanentFailure,"Backup scope/policy mismatch; no external action.");
  return inner.Execute(execution with {Audit=audit});
 }
}

public static class BackupDispatch {
 public static DispatchResult[] Run(BackupSettings settings,IAmazonDynamoDB ddb,IAmazonS3 s3,IAmazonSimpleNotificationService sns,
  string[] ids,string invocation,Func<DateTimeOffset> now,CancellationToken token) {
  settings.Validate();
  if(ids is null || ids.Length is <1 or >20 || ids.Any(x=>x is null || !System.Text.RegularExpressions.Regex.IsMatch(x,"^[a-f0-9]{64}$")) || ids.Distinct().Count()!=ids.Length)
   throw new ArgumentException("At most20 unique stored effect IDs required.");
  using var scoped=new ScopedDynamoClient(ddb,token);var store=new DynamoStore(scoped,settings.Dynamo,settings.Storage);
  using var archiveClient=new ScopedArchiveClient(s3,settings.Region,token);
  var processor=new SignalProcessor(store,new IncidentReducer(new Ecs.Backup.Sentinel.BackupIncidentPolicy(settings.Key)),settings.Storage);
  var notice=new SnsNoticeAdapter(sns,settings,token);var ack=new AuditAcknowledgement();
  var routes=new Dictionary<EffectKind,IEffectAdapter>{[EffectKind.OpenIncident]=ack,[EffectKind.RecordIncidentEvidence]=ack,
   [EffectKind.EscalateIncident]=notice,[EffectKind.ResolveIncident]=settings.NotificationMode=="EscalationAndRecovery"?notice:ack,
   [EffectKind.ScheduleRecoveryCheck]=new DeferredCheckAdapter(store,processor,now)};
  var gate=new BackupEffectGate(store,settings,new EffectRouter(routes,new S3ArchiveAdapter(archiveClient,settings.Archive)));
  var dispatch=new OutboxDispatcher(store,gate,new(TimeSpan.FromSeconds(30),TimeSpan.FromSeconds(10),3,false),now);
  var results=new List<DispatchResult>();
  foreach(var id in ids) {
   token.ThrowIfCancellationRequested();var entry=store.ReadEffect(id);
   if(entry is null || entry.AggregateKey!=StorageKeys.Aggregate(settings.Key)) {results.Add(new(id,null,"Absent or foreign backup work; no claim."));continue;}
   if(entry.Kind==WorkKind.DomainEffect && (entry.Intent is null || !routes.ContainsKey(entry.Intent.Kind))) {
    // No NAT RecoveryCheckWorker or provider. Unsupported work remains visible, not falsely completed.
    results.Add(new(id,null,"Unsupported backup work preserved pending; no provider invoked."));continue;
   }
   results.Add(dispatch.Dispatch(id,invocation));
  }
  return results.ToArray();
 }
}

// Only the two original archive adapter operations are supported; borrowed client is not disposed.
public sealed class ScopedArchiveClient(IAmazonS3 inner,string region,CancellationToken budget) : AmazonS3Client(new AnonymousAWSCredentials(),
 new AmazonS3Config {RegionEndpoint=Amazon.RegionEndpoint.GetBySystemName(region),MaxErrorRetry=0,HttpClientFactory=new RejectProxyNetwork()}) {
 public override async Task<PutObjectResponse> PutObjectAsync(PutObjectRequest request,CancellationToken ct=default) {
  using var linked=CancellationTokenSource.CreateLinkedTokenSource(budget,ct);linked.Token.ThrowIfCancellationRequested();return await inner.PutObjectAsync(request,linked.Token);
 }
 public override async Task<GetObjectResponse> GetObjectAsync(GetObjectRequest request,CancellationToken ct=default) {
  using var linked=CancellationTokenSource.CreateLinkedTokenSource(budget,ct);linked.Token.ThrowIfCancellationRequested();return await inner.GetObjectAsync(request,linked.Token);
 }
}
sealed class RejectProxyNetwork : HttpClientFactory {
 public override HttpClient CreateHttpClient(IClientConfig config)=>throw new InvalidOperationException("Unsupported archive proxy operation; no network fallback.");
}
