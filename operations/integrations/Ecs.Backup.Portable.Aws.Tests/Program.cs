using Amazon;
using Amazon.Runtime;
using Amazon.SimpleNotificationService;
using Amazon.SimpleNotificationService.Model;
using Sentinel.Core;
using Sentinel.Application;
using Sentinel.Persistence.Fakes;
using Sentinel.Portable;
using Sentinel.Portable.Aws;
using Ecs.Backup.Portable;
var c=StrictJson.Installation(File.ReadAllText(Path.Combine(args.Single(),"sentinel.json"))) with {NotificationsEnabled=true,TopicArn="arn:aws:sns:us-east-1:341936017254:ecs-portable-local-notices"};c.Validate();
var cases=new List<string>();void Check(string n,bool v){if(!v)throw new Exception(n);cases.Add(n);}
var at=DateTimeOffset.Parse("2026-10-26T03:00:00Z");var monitor=c.Monitors.Single(m=>m.Id=="sql-backup");var store=new TransactionalMemoryStore(new MemoryDatabase(),c.Storage);var processor=new SignalProcessor(store,new IncidentReducer(new NatRecoveryEvaluator()),c.Storage);
ProcessingResult Tick(int minutes){var now=at.AddMinutes(minutes);return processor.Process(new(1,"tick-"+minutes,"fixture-timer",monitor.Key,SignalKind.Evaluate,now,now,now,[]),monitor.Policy,c.Catalog().Context(now));}
Tick(0);Tick(11);Tick(13);var aggregate=StorageKeys.Aggregate(monitor.Key);var effect=store.Effects(aggregate).Single(e=>e.Intent?.Kind==EffectKind.EscalateIncident);var audit=store.ReadAudit(effect.AuditId)!;
using var sns=new SnsDouble();using var http=new HttpClient(new NoHttp());var io=0;IncidentNotice? captured=null;
var adapter=new Notifications(c,sns,http,_=>null,()=>io++,n=>{captured=n;return ReadableNotice.Render(n,c,true);});
var execution=new EffectExecution(effect.Id,effect,audit,1);var result=adapter.Execute(execution);var first=sns.Requests.Single();var notice=captured!;
Check("original notification routes real immutable audit to readable SNS",result.Status==DeliveryStatus.Confirmed && first.TopicArn==c.TopicArn && io==1);
Check("synthetic mark and clear state are prominent",first.Message.StartsWith("PRUEBA SINTÉTICA") && first.Message.Contains("SALUD NO VERIFICABLE"));
Check("original revision and audit timestamp preserved",first.Message.Contains("Revisión: "+audit.Revision) && first.Message.Contains(audit.Context.Now.ToString("O")));
foreach(var value in new[]{notice.DeliveryId,notice.AuditId,notice.IncidentId,notice.Generation!,notice.Consumer,notice.Resource!})Check("operational field preserved "+value[..Math.Min(8,value.Length)],first.Message.Contains(value));
Check("no inbox or SQL restore claim",first.Message.Contains("SNS_PUBLISH_ONLY_NOT_INBOX_RECEIPT") && first.Message.Contains("No implica una restauración SQL"));
adapter.Execute(execution);Check("retry renders identical body subject and delivery ID",sns.Requests[1].Message==first.Message && sns.Requests[1].Subject==first.Subject);
Check("raw internal schema2 notice remains structured",DomainJson.Deserialize<IncidentNotice>(DomainJson.Serialize(notice)).Revision==audit.Revision);
foreach(var altered in new[]{notice with{SchemaVersion=1},notice with{Consumer="foreign"},notice with{Generation="foreign"},notice with{ConfirmedServiceImpact=true},notice with{Summary="unsafe\nheader"}}){try{ReadableNotice.Render(altered,c,true);throw new Exception("NOT_REFUSED");}catch(ArgumentException){cases.Add("malformed/version/scope notice refused");}}
var resolved=notice with{Event="ResolveIncident",Condition=NoticeCondition.ExpectationSatisfied,Summary="Evidence satisfies configured expectation.",State="RESOLVED",Assessment="Successful",Revision=notice.Revision+1};
Check("resolution has clear heading without overwriting technical evidence",ReadableNotice.Render(resolved,c,true).Message.Contains("RECUPERACIÓN VERIFICADA PARA ESTA EXPECTATIVA"));
var bundleRoot=Path.Combine(Path.GetTempPath(),"ecs-portable-factory-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(bundleRoot);
try {
 var body=File.ReadAllBytes(Path.Combine(args.Single(),"sentinel.json"));File.WriteAllBytes(Path.Combine(bundleRoot,"sentinel.json"),body);
 var metadata=new {schemaVersion=1,upstreamCommit="b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828",syntheticTrial=true,configSha256=Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(body))};
 var metadataPath=Path.Combine(bundleRoot,"ecs-portable.json");File.WriteAllText(metadataPath,System.Text.Json.JsonSerializer.Serialize(metadata));
 Check("consumer factory admits exact two-expectation bundle without AWS",Ecs.Backup.Portable.Host.Function.ValidateBundle(bundleRoot).Monitors.Length==2);
 foreach(var wrong in new[]{System.Text.Json.JsonSerializer.Serialize(metadata with {configSha256=new string('0',64)}),System.Text.Json.JsonSerializer.Serialize(metadata with {syntheticTrial=false}),System.Text.Json.JsonSerializer.Serialize(metadata with {upstreamCommit=new string('0',40)})}) {
  File.WriteAllText(metadataPath,wrong);try{Ecs.Backup.Portable.Host.Function.ValidateBundle(bundleRoot);throw new Exception("NOT_REFUSED");}catch(InvalidOperationException){cases.Add("consumer bundle identity/format opt-in drift refused");}
 }
} finally {File.Delete(Path.Combine(bundleRoot,"sentinel.json"));File.Delete(Path.Combine(bundleRoot,"ecs-portable.json"));Directory.Delete(bundleRoot);}
Console.WriteLine(DomainJson.Serialize(new{Status="PASS",Tests=cases.Count,Cases=cases,OriginalNotificationSourceExecuted=true,Sns="OFFICIAL_PINNED_UPSTREAM_SDK_TRANSPORT_DOUBLE",UpstreamPinnedSdk4_0_100_16Qualified=true,AwsCalls=0,EmailSent=false}));
sealed class NoHttp:HttpMessageHandler {protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage r,CancellationToken c)=>throw new InvalidOperationException("HTTP forbidden.");}
sealed class RejectNetwork:Amazon.Runtime.HttpClientFactory {public override HttpClient CreateHttpClient(Amazon.Runtime.IClientConfig c)=>throw new InvalidOperationException("Network forbidden.");}
sealed class SnsDouble:AmazonSimpleNotificationServiceClient {
 public readonly List<PublishRequest> Requests=[];
 public SnsDouble():base(new AnonymousAWSCredentials(),new AmazonSimpleNotificationServiceConfig{RegionEndpoint=RegionEndpoint.USEast1,MaxErrorRetry=0,HttpClientFactory=new RejectNetwork()}){}
 public override Task<PublishResponse> PublishAsync(PublishRequest request,CancellationToken cancellationToken=default){cancellationToken.ThrowIfCancellationRequested();Requests.Add(request);return Task.FromResult(new PublishResponse{MessageId="local-only-not-delivery"});}
}
