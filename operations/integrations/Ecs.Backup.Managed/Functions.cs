using Amazon;
using Amazon.DynamoDBv2;
using Amazon.Lambda.Core;
using Amazon.Lambda.SQSEvents;
using Amazon.Runtime;
using Amazon.S3;
using Amazon.SimpleNotificationService;
using Sentinel.Application;
using Sentinel.Worker.Lambda;
[assembly: LambdaSerializer(typeof(Amazon.Lambda.Serialization.SystemTextJson.DefaultLambdaJsonSerializer))]
namespace Ecs.Backup.Managed;

public sealed record ManagedClients(IAmazonDynamoDB Dynamo,IAmazonS3 Archive,IAmazonSimpleNotificationService Notices);
public static class ManagedRuntime {
 public static BackupSettings Settings()=>BackupSettings.Read(Environment.GetEnvironmentVariable);
 public static ManagedClients Clients(BackupSettings settings) {
  // Executed in Lambda only. Rotating execution-role credentials, explicit region, no profile/endpoint inputs.
  var credentials=new EnvironmentVariablesAWSCredentials();var region=RegionEndpoint.GetBySystemName(settings.Region);
  return new(new AmazonDynamoDBClient(credentials,new AmazonDynamoDBConfig {RegionEndpoint=region,MaxErrorRetry=1,Timeout=TimeSpan.FromSeconds(5)}),
   new AmazonS3Client(credentials,new AmazonS3Config {RegionEndpoint=region,MaxErrorRetry=0,Timeout=TimeSpan.FromSeconds(5)}),
   new AmazonSimpleNotificationServiceClient(credentials,new AmazonSimpleNotificationServiceConfig {RegionEndpoint=region,MaxErrorRetry=0,Timeout=TimeSpan.FromSeconds(5)}));
 }
 public static CancellationTokenSource Budget(ILambdaContext context,TimeSpan? trialRemaining=null) {
  var token=new CancellationTokenSource();var available=context.RemainingTime-TimeSpan.FromSeconds(3);
  if(trialRemaining is { } cap && cap<available)available=cap;
  if(available<=TimeSpan.Zero)token.Cancel();else token.CancelAfter(available);return token;
 }
}
// The consumer entry assembly declares its serializer; original batch handling remains upstream.
public sealed class IngestFunction {
 private readonly Func<BackupSettings> settings;private readonly Func<BackupSettings,ManagedClients> clients;private readonly Func<DateTimeOffset> clock;
 private ManagedClients? warm;
 public IngestFunction():this(ManagedRuntime.Settings,ManagedRuntime.Clients,()=>DateTimeOffset.UtcNow) {}
 public IngestFunction(Func<BackupSettings> settings,Func<BackupSettings,ManagedClients> clients,Func<DateTimeOffset> clock) {this.settings=settings;this.clients=clients;this.clock=clock;}
 public async Task<SQSBatchResponse> Handler(SQSEvent batch,ILambdaContext context) {
  var config=settings();config.ValidateInvocation(context.InvokedFunctionArn,"ingest",clock());
  using var token=ManagedRuntime.Budget(context,config.ExpiresAt-clock());var sdk=warm??=clients(config);
  return await BackupComposition.Ingestion(config,sdk.Dynamo,token.Token,clock).Handle(batch,context.AwsRequestId,token.Token).ConfigureAwait(false);
 }
}
public sealed record DispatchRequest(string[] EffectIds);
public sealed class DispatchFunction {
 private readonly Func<BackupSettings> settings;private readonly Func<BackupSettings,ManagedClients> clients;private readonly Func<DateTimeOffset> clock;
 private ManagedClients? warm;
 public DispatchFunction():this(ManagedRuntime.Settings,ManagedRuntime.Clients,()=>DateTimeOffset.UtcNow) {}
 public DispatchFunction(Func<BackupSettings> settings,Func<BackupSettings,ManagedClients> clients,Func<DateTimeOffset> clock) {this.settings=settings;this.clients=clients;this.clock=clock;}
 public DispatchResult[] Handler(DispatchRequest request,ILambdaContext context) {
  var config=settings();config.ValidateInvocation(context.InvokedFunctionArn,"dispatch",clock());
  using var token=ManagedRuntime.Budget(context,config.ExpiresAt-clock());var sdk=warm??=clients(config);
  return BackupDispatch.Run(config,sdk.Dynamo,sdk.Archive,sdk.Notices,request.EffectIds,context.AwsRequestId,clock,token.Token);
 }
}
