using System.Security.Cryptography;
using System.Text.Json;
using Amazon.Lambda.Core;
using Amazon.Lambda.SQSEvents;
using Sentinel.Portable;
using Sentinel.Operations;
using Sentinel.Portable.Lambda;
using Amazon;
using Amazon.DynamoDBv2;
using Amazon.S3;
using Sentinel.Core;
using Sentinel.Persistence.DynamoDb;
using Sentinel.Persistence.S3;
[assembly: LambdaSerializer(typeof(Amazon.Lambda.Serialization.SystemTextJson.DefaultLambdaJsonSerializer))]
namespace Ecs.Backup.Portable.Host;
public sealed class Function {
 private readonly Sentinel.Portable.Lambda.Function inner;
 public Function() {
  var config=ValidateBundle(AppContext.BaseDirectory);
  inner=new(n=>ReadableNotice.Render(n,config,true),(client,options,now)=>new CurrentBacklog(client,options).Read(now)); // Closed callbacks; no caller override.
 }
 public static Installation ValidateBundle(string root) {
  var raw=File.ReadAllBytes(Path.Combine(root,"sentinel.json"));
  using var doc=JsonDocument.Parse(File.ReadAllBytes(Path.Combine(root,"ecs-portable.json")));var p=doc.RootElement;
  if(p.EnumerateObject().Count()!=4 || p.GetProperty("schemaVersion").GetInt32()!=1 || p.GetProperty("upstreamCommit").GetString()!="b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828" || !p.GetProperty("syntheticTrial").GetBoolean() ||
   p.GetProperty("configSha256").GetString()!=Convert.ToHexStringLower(SHA256.HashData(raw)))throw new InvalidOperationException("Exact synthetic bundle metadata required.");
  var config=StrictJson.Installation(System.Text.Encoding.UTF8.GetString(raw));
  var sql=config.Monitors.Where(m=>m.Sources.SequenceEqual(new[]{"sql-observer"})).ToArray();
  var nat=config.Monitors.Where(m=>!m.Sources.SequenceEqual(new[]{"sql-observer"})).ToArray();
  if(config.Account!="341936017254" || config.Region!="us-east-1" || sql.Length!=2 || sql.Count(m=>m.Kind=="sql-backup" && m.Selector=="full" && m.RequiredAssurance==Assurance.Artifact)!=1 || sql.Count(m=>m.Kind=="report" && m.RequiredAssurance==Assurance.Reported)!=1 || sql.Any(m=>m.Model!=MonitorModel.Freshness) || nat.Length>1 || nat.Any(m=>m.Id!="nat-a-egress" || m.Kind!="report" || m.Resource!="nat/dev/a" || m.Generation!="lt4-e13v6" || m.RequiredAssurance!=Assurance.Reported || !m.Sources.SequenceEqual(new[]{"nat-observer"})) || config.MaxJobs!=4 || config.MaxRequests!=64 || config.WebhookEnvironment is not null)throw new InvalidOperationException("Closed DEV backup/NAT observation profile required.");
  return config;
 }
 static (Installation Config,DynamoOptions Options,ArchiveOptions Archive) Bind(TickEvent request,ILambdaContext context,string component) {
  var c=ValidateBundle(AppContext.BaseDirectory);var arn=context.InvokedFunctionArn.Split(':');
  if(request.Deployment!=c.Deployment || arn.Length<7 || arn[3]!=c.Region || arn[4]!=c.Account || arn[6]!=c.Deployment+"-"+component)throw new ArgumentException("Invocation outside own component.");
  string Env(string key)=>Environment.GetEnvironmentVariable(key)??throw new ArgumentException("Missing runtime binding.");
  return(c,new(Env("SENTINEL_TABLE"),c.Project,c.Environment,c.Consumer,PageSize:64),new(Env("SENTINEL_ARCHIVE"),c.Project,c.Environment,c.Consumer,KmsKeyId:Env("SENTINEL_ARCHIVE_KMS_KEY")));
 }
 public TickSummary Tick(TickEvent request,ILambdaContext context) {
  if(request.Mode!="compensate-approved-four-archives")return inner.Tick(request,context);
  var b=Bind(request,context,"worker");
  using var ddb=new AmazonDynamoDBClient(new AmazonDynamoDBConfig{RegionEndpoint=RegionEndpoint.USEast1,MaxErrorRetry=0,Timeout=TimeSpan.FromSeconds(5)});
  using var s3=new AmazonS3Client(new AmazonS3Config{RegionEndpoint=RegionEndpoint.USEast1,MaxErrorRetry=0,Timeout=TimeSpan.FromSeconds(5)});
  var compensation=new ArchiveCompensation(ddb,s3,b.Options,b.Archive);var receipts=compensation.Execute(DateTimeOffset.UtcNow);
  context.Logger.LogLine(DomainJson.Serialize(new{type="SentinelArchiveCompensation",receipts,compensation.Requests,originalRecordsChanged=0,notificationsSent=0}));
  return new("ArchiveCompensationVerified",receipts.Count,receipts.Count,0,receipts.Count,0);
 }
 public Task<SQSBatchResponse> Ingest(SQSEvent request,ILambdaContext context)=>inner.Ingest(request,context);
 public HealthAssessment Watchdog(TickEvent request,ILambdaContext context) {
  if(request.Mode!="watchdog")throw new ArgumentException("Invalid watchdog trigger.");
  var b=Bind(request,context,"watchdog");var c=b.Config;
  using var ddb=new AmazonDynamoDBClient(new AmazonDynamoDBConfig{RegionEndpoint=RegionEndpoint.USEast1,MaxErrorRetry=0,Timeout=TimeSpan.FromSeconds(5)});
  using var s3=new AmazonS3Client(new AmazonS3Config{RegionEndpoint=RegionEndpoint.USEast1,MaxErrorRetry=0,Timeout=TimeSpan.FromSeconds(5)});
  var scope=new OperationalScope(c.Project,c.Environment,c.Consumer,"worker","portable");
  var raw=new DynamoOperationalStore(ddb,b.Options).Read(scope);var now=DateTimeOffset.UtcNow;
  var compensation=new ArchiveCompensation(ddb,s3,b.Options,b.Archive);
  var verified=b.Options.Namespace=="NS#b752b39384784041f4d8fe445ceb7002180c236cfa595219f87701424ae032b2"?compensation.VerifiedCount(now):0;
  var result=HealthEvaluator.Evaluate(scope,ArchiveCompensation.CurrentHealthView(raw,verified),c.Operations,now);
  context.Logger.LogLine(HealthMetric(result));
  context.Logger.LogLine(DomainJson.Serialize(new{type="SentinelHealth",deployment=c.Deployment,healthy=result.State is HealthState.HEALTHY_ACTIVE or HealthState.HEALTHY_IDLE?1:0,result,backlog=raw?.Backlog,historicalPermanentFailures=raw?.UnresolvedFailures,verifiedArchiveCompensations=verified,activePermanentFailures=raw is null?(int?)null:raw.UnresolvedFailures-verified,requests=compensation.Requests+1}));
  return result;
 }
 public static string HealthMetric(HealthAssessment result)=>"SentinelHealthMetric "+(result.State is HealthState.HEALTHY_ACTIVE or HealthState.HEALTHY_IDLE?"1":"0");
 public int Cleanup(TickEvent request,ILambdaContext context)=>inner.Cleanup(request,context);
}
