using System.Collections.Immutable;
using System.Text.Json.Nodes;
using Amazon;
using Amazon.Runtime;
using Amazon.Lambda.Core;
using Amazon.Lambda.SQSEvents;
using Amazon.Lambda.Serialization.SystemTextJson;
using Amazon.SimpleNotificationService;
using Amazon.SimpleNotificationService.Model;
using Sentinel.Core;
using Sentinel.Application;
using Sentinel.Ingestion;
using Sentinel.Persistence.Fakes;
using Sentinel.Portable;
using Sentinel.Portable.Aws;
using Ecs.Backup.Portable;
var root=args.Single();var stages=JsonNode.Parse(File.ReadAllText(Path.Combine(root,"flow.json")))!.AsArray();
var config=StrictJson.Installation(File.ReadAllText(Path.Combine(root,"sentinel.json")));var backup=config.Monitors.Single(m=>m.Id=="sql-backup");var telemetry=config.Monitors.Single(m=>m.Id=="sql-telemetry");
var checks=new List<string>();void Check(string label,bool ok){if(!ok)throw new Exception(label);checks.Add(label);}
var now=DateTimeOffset.Parse(stages[0]!["at"]!.GetValue<string>());var store=new TransactionalMemoryStore(new MemoryDatabase(),config.Storage);var processor=new SignalProcessor(store,new IncidentReducer(new NatRecoveryEvaluator()),config.Storage);var catalog=config.Catalog();
foreach(var m in config.Monitors)Check("actual expectation persisted "+m.Id,MonitorBootstrap.Ensure(m,store,processor,catalog,now).Status==ProcessingStatus.Committed);
var ingress=new IngestionProcessor(new ReportNormalizer(config,k=>store.Read(StorageKeys.Aggregate(k))?.Head.Epoch??1),new(config.Account,config.Region,config.Project,config.Environment,["sql-observer"],config.Monitors.Select(m=>m.Key).ToImmutableArray()),_=>new(processor),k=>catalog.Resolve(k).Policy,contexts:catalog.Context);
var queue="arn:aws:sqs:"+config.Region+":"+config.Account+":"+config.Deployment+"-reports";
var handler=new Sentinel.Worker.Lambda.Function(ingress,()=>now,queue);var serializer=new DefaultLambdaJsonSerializer();
SQSEvent Batch(JsonArray entries){var messages=entries.Select((n,i)=>{var e=n!.AsObject();var envelope=new JsonObject{["version"]="0",["id"]="local-event-"+i,["source"]=e["Source"]!.DeepClone(),["detail-type"]=e["DetailType"]!.DeepClone(),["account"]=config.Account,["region"]=config.Region,["detail"]=JsonNode.Parse(e["Detail"]!.GetValue<string>())};return new SQSEvent.SQSMessage{MessageId="message-"+i,Body=envelope.ToJsonString(),EventSource="aws:sqs",EventSourceArn=queue,Attributes=new(){["ApproximateReceiveCount"]="1"}};}).ToList();using var json=new MemoryStream();serializer.Serialize(new SQSEvent{Records=messages},json);json.Position=0;return serializer.Deserialize<SQSEvent>(json);}
ProcessingResult Evaluate(MonitorDefinition m)=>processor.Process(new(1,DomainJson.StableId("local-scheduled-check",m.Id,now.ToString("O")),"timer",m.Key,SignalKind.Evaluate,now,now,now,[]),m.Policy,catalog.Context(now));
using var sns=new Sns();using var http=new HttpClient(new NeverHttp());var notices=new List<IncidentNotice>();var adapter=new Notifications(config,sns,http,_=>null,()=>{},n=>{notices.Add(n);return ReadableNotice.Render(n,config,true);});
void Notice(EffectKind kind){var e=store.Effects(StorageKeys.Aggregate(backup.Key)).Last(e=>e.Intent?.Kind==kind);var audit=store.ReadAudit(e.AuditId)!;Check("original SNS adapter accepted local double "+kind,adapter.Execute(new(e.Id,e,audit,1)).Status==DeliveryStatus.Confirmed);}
var first=Batch(stages[0]!["entries"]!.AsArray());Check("actual SQS handler ACKs accepted packaged reports",(await handler.Handler(first,new Context())).BatchItemFailures.Count==0);
var revision=store.Read(StorageKeys.Aggregate(backup.Key))!.Head.Revision;Check("redelivery ACK is deduplicated",(await handler.Handler(first,new Context())).BatchItemFailures.Count==0 && store.Read(StorageKeys.Aggregate(backup.Key))!.Head.Revision==revision);
var start=now;now=start.AddMinutes(11);Evaluate(backup);now=start.AddMinutes(13);Evaluate(backup);Check("missing opens UNKNOWN without claiming SQL failure",store.Read(StorageKeys.Aggregate(backup.Key))!.Head.State==IncidentState.ESCALATED && store.History(StorageKeys.Aggregate(backup.Key)).Last().Reduction.Decision.Assessment!.Status==RecoveryStatus.InsufficientEvidence);Notice(EffectKind.EscalateIncident);
foreach(var n in stages.Skip(1)){now=DateTimeOffset.Parse(n!["at"]!.GetValue<string>());Check("packaged "+n["status"]+" accepted by actual handler",(await handler.Handler(Batch(n["entries"]!.AsArray()),new Context())).BatchItemFailures.Count==0);if(n["status"]!.GetValue<string>()!="HEALTHY")Check("unconfirmed/stale report cannot heal",store.Read(StorageKeys.Aggregate(backup.Key))!.Head.State!=IncidentState.RESOLVED);}
Check("fresh valid artifact resolves the same backup incident",store.Read(StorageKeys.Aggregate(backup.Key))!.Head.State==IncidentState.RESOLVED);Notice(EffectKind.ResolveIncident);
Check("exactly attention and recovery text, no inbox claim",sns.Messages.Count==2 && sns.Messages.All(m=>m.Message.StartsWith("PRUEBA SINTÉTICA") && m.Message.Contains("SNS_PUBLISH_ONLY_NOT_INBOX_RECEIPT")) && notices[0].IncidentId==notices[1].IncidentId && notices.All(n=>n.SchemaVersion==2));
Check("no NAT functional probe or healing adapter requested",config.Monitors.All(m=>store.Effects(StorageKeys.Aggregate(m.Key)).All(e=>e.Intent?.Kind!=EffectKind.RequestFunctionalProbe)));
Check("future supervision remains visible, no drained claim",store.Effects(StorageKeys.Aggregate(backup.Key)).Any(e=>e.Intent?.Kind==EffectKind.ScheduleRecoveryCheck && e.Status==OutboxStatus.Pending));
var wrong=Batch(stages.Last()!["entries"]!.AsArray());wrong.Records[0].EventSourceArn=queue+"-foreign";Check("foreign queue is not ACKed",(await handler.Handler(wrong,new Context())).BatchItemFailures.Single().ItemIdentifier==wrong.Records[0].MessageId);
File.WriteAllText(Path.Combine(root,"readable-notices.json"),DomainJson.Serialize(sns.Messages));File.WriteAllText(Path.Combine(root,"handler-flow-result.json"),DomainJson.Serialize(new{Status="PASS",Tests=checks.Count,Cases=checks,Handler="ORIGINAL_SENTINEL_WORKER_LAMBDA_HANDLER",Storage="ORIGINAL_MEMORY_FAKE",Sns="PINNED_SDK_TRANSPORT_DOUBLE",PortableOuterAwsCompositionInvoked=false,AwsCalls=0,EmailSent=false}));Console.WriteLine(File.ReadAllText(Path.Combine(root,"handler-flow-result.json")));
sealed class NeverHttp:HttpMessageHandler{protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage r,CancellationToken t)=>throw new Exception("No HTTP");}
sealed class NeverNetwork:Amazon.Runtime.HttpClientFactory{public override HttpClient CreateHttpClient(Amazon.Runtime.IClientConfig c)=>throw new Exception("No network");}
sealed class Sns:AmazonSimpleNotificationServiceClient{public readonly List<PublishRequest> Messages=[];public Sns():base(new AnonymousAWSCredentials(),new AmazonSimpleNotificationServiceConfig{RegionEndpoint=RegionEndpoint.USEast1,MaxErrorRetry=0,HttpClientFactory=new NeverNetwork()}){}public override Task<PublishResponse> PublishAsync(PublishRequest r,CancellationToken t=default){Messages.Add(r);return Task.FromResult(new PublishResponse{MessageId="local-acceptance-"+Messages.Count});}}
sealed class Logger:ILambdaLogger{public void Log(string m){}public void LogLine(string m){}}
sealed class Context:ILambdaContext{public string AwsRequestId=>"local-handler-request";public IClientContext ClientContext=>null!;public string FunctionName=>"local-ingestion";public string FunctionVersion=>"local";public ICognitoIdentity Identity=>null!;public string InvokedFunctionArn=>"local";public string LogGroupName=>"local";public string LogStreamName=>"local";public int MemoryLimitInMB=>512;public TimeSpan RemainingTime=>TimeSpan.FromSeconds(60);public ILambdaLogger Logger=>new Logger();}
