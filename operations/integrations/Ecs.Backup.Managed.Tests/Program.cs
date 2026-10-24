using System.Net;
using System.Text.Json.Nodes;
using Amazon;
using Amazon.Runtime;
using Amazon.DynamoDBv2;
using Amazon.DynamoDBv2.Model;
using Amazon.S3;
using Amazon.SimpleNotificationService;
using Amazon.SimpleNotificationService.Model;
using Amazon.Lambda.Core;
using Amazon.Lambda.SQSEvents;
using Ecs.Backup.Managed;
using Sentinel.Adapters.Tests;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Persistence.DynamoDb;
using Sentinel.Persistence.S3;

var fixtures=Directory.GetFiles(args.Single(),"*.json").ToDictionary(x=>Path.GetFileNameWithoutExtension(x)!,File.ReadAllText);
var cases=new List<string>();
void Check(string name,bool valid) {if(!valid)throw new Exception("FAILED: "+name);cases.Add(name);}
async Task Reject(string name,Func<Task> action) {try {await action();throw new Exception("NOT_REJECTED");}catch(ArgumentException){Check(name,true);}}
string Change(string body,string field,JsonNode? value) {var node=JsonNode.Parse(body)!.AsObject();node[field]=value;return node.ToJsonString();}
var r=new Rig();
Check("explicit test settings validate",r.Settings.Dynamo.Namespace.StartsWith("NS#"));
Check("namespace matches Terraform JSON SHA256 contract",r.Settings.Dynamo.Namespace=="NS#a44c67745b62d912a7ba254fc0ac38100716f3869e2ac3ed72929c74878c4654" && r.Settings.Archive.Prefix=="sentinel/v3/a44c67745b62d912a7ba254fc0ac38100716f3869e2ac3ed72929c74878c4654");
var result=await r.Send(fixtures["failed"]);
Check("original SQS Lambda ACKs committed failure",result.BatchItemFailures.Count==0 && r.Head.State==IncidentState.ESCALATED);
Check("original DynamoStore commits physical schema3 transactions",r.Ddb.Inner.Writes.Count>0 && r.Ddb.Inner.Rows.Values.Where(x=>x.ContainsKey("Data")).All(x=>x["Schema"].N=="3"));
Check("normalizer and commit SDK reads carry invocation token",r.Ddb.Tokens.Count>0 && r.Ddb.Tokens.All(x=>x.CanBeCanceled));
var effectCount=r.Effects.Length;var revision=r.Head.Revision;
Check("valid unchanged candidate ACK has no transaction",(await r.Send(fixtures["failed-unchanged"])).BatchItemFailures.Count==0 && r.Head.Revision==revision);
r.Restart();
Check("new runtime reuses persisted receipt and deduplicates",(await r.Send(fixtures["failed"])).BatchItemFailures.Count==0 && r.Head.Revision==revision && r.Effects.Length==effectCount);
var receipts=r.Ddb.Inner.Rows.Values.Where(x=>x["SK"].S.StartsWith("R#")).Select(PhysicalLayout.Payload<ProcessedReceipt>).ToArray();
Check("explicit one-day test retention reaches real DynamoStore",receipts.All(x=>x.ExpiresAt-x.ProcessedAt==TimeSpan.FromDays(1)));
var before=r.Ddb.Inner.Writes.Count;
var foreign=r.Batch(fixtures["missing"]);foreign.Records[0].EventSourceArn=r.Settings.QueueArn+"-foreign";
Check("foreign SQS ARN refused before writes",(await r.Ingest.Handler(foreign,r.Context("ingest"))).BatchItemFailures.Count==1 && r.Ddb.Inner.Writes.Count==before);
foreign=r.Batch(fixtures["missing"]);foreign.Records[0].EventSource="aws:events";
Check("foreign transport refused before writes",(await r.Ingest.Handler(foreign,r.Context("ingest"))).BatchItemFailures.Count==1 && r.Ddb.Inner.Writes.Count==before);
var duplicate=r.Batch(fixtures["missing"]);duplicate.Records.Add(duplicate.Records[0]);
await Reject("duplicate batch IDs reject whole batch before writes",()=>r.Ingest.Handler(duplicate,r.Context("ingest")));Check("duplicate invalid batch leaves writes unchanged",r.Ddb.Inner.Writes.Count==before);
var partial=r.Batch("{bad-json");partial.Records.Add(new(){MessageId="good-suppressed",Body=fixtures["failed-unchanged"],EventSource="aws:sqs",EventSourceArn=r.Settings.QueueArn});
var partialResponse=await r.Ingest.Handler(partial,r.Context("ingest"));
Check("original partial ACK retries poison only",partialResponse.BatchItemFailures.Select(x=>x.ItemIdentifier).SequenceEqual(new[]{"message"}) && r.Ddb.Inner.Writes.Count==before);
Check("real-check claim refused in synthetic-only host",(await r.Send(Change(Change(fixtures["missing"],"Evaluation",JsonValue.Create("CHECK_COMMAND_RESULT")),"CheckInvoked",JsonValue.Create(true)))).BatchItemFailures.Count==1);
Check("expired invocation retries without SDK writes",(await r.Ingest.Handler(r.Batch(fixtures["failed-unchanged"]),r.Context("ingest",TimeSpan.Zero))).BatchItemFailures.Count==1 && r.Ddb.Inner.Writes.Count==before);
await Reject("wrong function/account binding refused",()=>r.Ingest.Handler(r.Batch(fixtures["missing"]),r.Context("ingest") with {InvokedFunctionArn="arn:aws:lambda:us-east-1:111111111111:function:foreign"}));
var unknown=new Rig();await unknown.Send(fixtures["unknown"]);Check("durable UNKNOWN stays uncertain",unknown.Head.State==IncidentState.RECOVERING);
await unknown.Send(fixtures["recovered"]);Check("durable first health requires confirmation",unknown.Head.State==IncidentState.AUTO_RECOVERED);
await unknown.Send(fixtures["baseline"]);Check("suppressed genuine second health reaches original reducer",unknown.Head.State==IncidentState.RESOLVED);
foreach(var status in new[]{"missing","stale"}) {var x=new Rig();Check("durable "+status+" opens failure",(await x.Send(fixtures[status])).BatchItemFailures.Count==0 && x.Head.State==IncidentState.ESCALATED);}
await r.Send(fixtures["unknown"]);Check("UNKNOWN cannot heal existing incident",r.Head.State==IncidentState.ESCALATED);
await r.Send(fixtures["recovered"]);Check("durable recovery resolves original epoch",r.Head.State==IncidentState.RESOLVED);
await r.Send(fixtures["recurrence"]);var epoch=r.Head.Epoch;await r.Send(fixtures["recovered"]);Check("old recovery receipt cannot heal recurrence",epoch==2 && r.Head.Epoch==2 && r.Head.State==IncidentState.ESCALATED);
var uncertain=new Rig();uncertain.Ddb.Inner.WriteFailure=new TimeoutException("synthetic provider detail");uncertain.Ddb.Inner.FailureAfterCommit=true;
Check("commit timeout reconciles receipt/audit before ACK",(await uncertain.Send(fixtures["failed"])).BatchItemFailures.Count==0 && uncertain.Head.Revision==1);
var unavailable=new Rig();unavailable.Ddb.Inner.WriteFailure=new TimeoutException("synthetic failure");
Check("uncommitted timeout is retryable",(await unavailable.Send(fixtures["failed"])).BatchItemFailures.Count==1 && unavailable.Ddb.Inner.Rows.Count==0);

// Real original outbox fencing and S3 archive, SDK doubles only.
var d=new Rig();await d.Send(fixtures["failed"]);var escalation=d.Effects.Single(e=>e.Intent?.Kind==EffectKind.EscalateIncident);var archive=d.Effects.First(e=>e.Kind==WorkKind.ArchiveDecision);
var dispatch=d.Dispatch([escalation.Id]);
Check("original outbox records known SNS publish ACK",dispatch.Single().Completion==CompletionStatus.Recorded && d.Store.ReadEffect(escalation.Id)!.Status==OutboxStatus.Confirmed);
Check("SNS request is only exact topic with no recipient override",d.Sns.Requests.Count==1 && d.Sns.Requests[0].TopicArn==d.Settings.TopicArn && d.Sns.Requests[0].TargetArn is null && d.Sns.Requests[0].PhoneNumber is null);
Check("SNS body sanitized and honest about synthetic acceptance",d.Sns.Requests[0].Message.Contains("SNS_PUBLISH_ONLY_NOT_INBOX_RECEIPT") && !d.Sns.Requests[0].Message.Contains("Password"));
var failedRequest=d.Sns.Requests[0];
Check("email starts with a visible synthetic warning",failedRequest.Message.StartsWith("PRUEBA SINTÉTICA\n") && failedRequest.Subject.StartsWith("PRUEBA SINTETICA | "));
Check("email is plain text rather than the internal JSON",!failedRequest.Message.TrimStart().StartsWith('{') && !failedRequest.Message.Contains("<html") && failedRequest.MessageStructure is null);
Check("readable facts precede technical identifiers",failedRequest.Message.IndexOf("Estado:")<failedRequest.Message.IndexOf("Servicio:") && failedRequest.Message.IndexOf("Motivo registrado:")<failedRequest.Message.IndexOf("DATOS TÉCNICOS") && failedRequest.Message.IndexOf("DATOS TÉCNICOS")<failedRequest.Message.IndexOf("Efecto:"));
var structured=DomainJson.Deserialize<BackupNoticeEvidence>(failedRequest.MessageAttributes["BackupEvidence"].StringValue);
Check("structured sanitized evidence remains internal",failedRequest.MessageAttributes["BackupEvidence"].DataType=="String" && structured.SyntheticTrial && structured.SchemaVersion==1 && structured.EffectId==escalation.Id && structured.BackupStatus=="FAILED");
Check("failed reason comes from validated observer code",failedRequest.Message.Contains("LAST_ATTEMPT_FAILED") && failedRequest.Message.Contains("El observador informó un intento fallido."));
Check("human email separates evidence from inbox acceptance",failedRequest.Message.Contains("no acredita recepción en el buzón") && failedRequest.Message.Contains("no acredita un fallo real ni una restauración SQL"));
foreach(var (status,code,state) in new[]{("FAILED","LAST_ATTEMPT_FAILED","FALLO"),("MISSING","NO_REMOTE_COMMIT","AUSENTE"),("STALE","REMOTE_BACKUP_TOO_OLD","ANTIGUO"),("UNKNOWN","REMOTE_STORAGE_NOT_CHECKED","SIN DATOS SUFICIENTES"),("HEALTHY","RECENT_REMOTE_COMMIT","SANO")}) {
 var rendered=BackupNoticeText.Format(structured with {BackupStatus=status},code,DateTimeOffset.Parse("2026-10-23T17:00:00Z"));
 Check("readable "+status+" uses only compatible observed facts",rendered.Message.Contains("Estado: "+state) && rendered.Message.Contains("Código del recibo: "+code) && !rendered.Message.Contains("NO_DISPONIBLE"));
}
var hidden=BackupNoticeText.Format(structured,"Password=synthetic-do-not-leak",DateTimeOffset.Parse("2026-10-23T17:00:00Z"));
Check("incompatible raw reason is not rendered or invented",!hidden.Message.Contains("synthetic-do-not-leak") && hidden.Message.Contains("NO_DISPONIBLE") && hidden.Message.Contains("no se infiere una causa"));
var maxTitle=BackupNoticeText.Format(structured with {SenderLabel=new string('x',40)},"LAST_ATTEMPT_FAILED",DateTimeOffset.Parse("2026-10-23T17:00:00Z"));
Check("SNS title fits byte limit and has no controls",System.Text.Encoding.UTF8.GetByteCount(maxTitle.Subject)<=100 && !maxTitle.Subject.Any(char.IsControl));
await Reject("renderer cannot relabel a non-synthetic notice",()=>Task.Run(()=>BackupNoticeText.Format(structured with {SyntheticTrial=false},"LAST_ATTEMPT_FAILED",DateTimeOffset.Parse("2026-10-23T17:00:00Z"))));
d.Dispatch([escalation.Id]);Check("confirmed durable outbox does not publish twice",d.Sns.Requests.Count==1);
var archiveResult=d.Dispatch([archive.Id]);Check("original S3 archive confirms only after readback",archiveResult[0].Completion==CompletionStatus.Recorded && d.S3.Objects.Count==1 && d.S3.Gets.Count==1 && d.Store.ReadAudit(archive.AuditId)!.ArchivedAt is not null);
Check("archive prefix and SSE-S3 stay trial-local",d.S3.Puts.All(x=>x.Key.StartsWith(d.Settings.Archive.Prefix+"/") && x.ServerSideEncryptionMethod==ServerSideEncryptionMethod.AES256));
var probe=d.Effects.First(e=>e.Intent?.Kind==EffectKind.RequestFunctionalProbe);var writes=d.Ddb.Inner.Writes.Count;var unsupported=d.Dispatch([probe.Id]);
Check("functional probe remains pending with no claim or NAT worker",unsupported[0].Completion is null && d.Store.ReadEffect(probe.Id)!.Status==OutboxStatus.Pending && d.Ddb.Inner.Writes.Count==writes);
var expected=d.Store.ReadAudit(archive.AuditId)!;var adapter=new S3ArchiveAdapter(d.S3,d.Settings.Archive);d.S3.Objects[d.Settings.Archive.Bucket+"/"+adapter.Key(expected)]=[1,2,3];
Check("corrupt immutable archive rejected",adapter.Execute(new(archive.Id,archive,expected,1)).Status==DeliveryStatus.PermanentFailure);
var lostArchive=new Rig();await lostArchive.Send(fixtures["failed"]);var a=lostArchive.Effects.First(e=>e.Kind==WorkKind.ArchiveDecision);
lostArchive.S3.NextPutFailure=new TimeoutException();lostArchive.S3.FailureAfterPut=true;lostArchive.Dispatch([a.Id]);
Check("archive timeout preserves uncertainty after possible PUT",lostArchive.Store.ReadEffect(a.Id)!.Status==OutboxStatus.Uncertain && lostArchive.S3.Objects.Count==1);
lostArchive.Now=lostArchive.Now.AddSeconds(11);lostArchive.Dispatch([a.Id]);Check("archive retry verifies same immutable object",lostArchive.S3.Objects.Count==1 && lostArchive.Store.ReadEffect(a.Id)!.Status==OutboxStatus.Confirmed);
var snsUnknown=new Rig();await snsUnknown.Send(fixtures["failed"]);var e=snsUnknown.Effects.First(e=>e.Intent?.Kind==EffectKind.EscalateIncident);snsUnknown.Sns.Failure=new TimeoutException("synthetic secret-like detail");snsUnknown.Dispatch([e.Id]);
Check("unknown SNS acceptance not marked delivered",snsUnknown.Store.ReadEffect(e.Id)!.Status==OutboxStatus.Uncertain && !snsUnknown.Store.ReadEffect(e.Id)!.LastResult!.Contains("secret-like"));
var sn=new SnsNoticeAdapter(snsUnknown.Sns,snsUnknown.Settings,CancellationToken.None);Check("SNS Standard never claims idempotency",!sn.SupportsIdempotency);
var audit=snsUnknown.Store.ReadAudit(e.AuditId)!;var execution=new EffectExecution(e.Id,e,audit,1);
snsUnknown.Sns.Failure=new AmazonSimpleNotificationServiceException("private denied"){StatusCode=HttpStatusCode.Forbidden};Check("SNS denial sanitized permanent no alternate",sn.Execute(execution).Status==DeliveryStatus.PermanentFailure);
snsUnknown.Sns.Failure=new AmazonSimpleNotificationServiceException("private throttled"){StatusCode=HttpStatusCode.TooManyRequests};Check("SNS throttling retryable",sn.Execute(execution).Status==DeliveryStatus.RetryableFailure);
snsUnknown.Sns.Failure=new AmazonSimpleNotificationServiceException("private 5xx"){StatusCode=HttpStatusCode.ServiceUnavailable};Check("SNS 5xx acceptance unknown",sn.Execute(execution).Status==DeliveryStatus.Unknown);
snsUnknown.Sns.Failure=new AmazonClientException("synthetic-private-provider-detail");var clientUnknown=sn.Execute(execution);Check("SNS client network failure remains sanitized unknown",clientUnknown.Status==DeliveryStatus.Unknown && !clientUnknown.Detail.Contains("private-provider"));
snsUnknown.Sns.MessageId="";Check("empty SNS receipt is unknown",sn.Execute(execution).Status==DeliveryStatus.Unknown);snsUnknown.Sns.MessageId="synthetic-message-id";
using var cancelled=new CancellationTokenSource();cancelled.Cancel();var calls=snsUnknown.Sns.Requests.Count;
Check("cancelled SNS not attempted",new SnsNoticeAdapter(snsUnknown.Sns,snsUnknown.Settings,cancelled.Token).Execute(execution).Status==DeliveryStatus.RetryableFailure && snsUnknown.Sns.Requests.Count==calls);
var gate=new BackupEffectGate(snsUnknown.Store,snsUnknown.Settings,sn);calls=snsUnknown.Sns.Requests.Count;
Check("foreign policy cannot reach SNS",gate.Execute(execution with {Audit=audit with {Policy=audit.Policy with {Nat=audit.Policy.Nat with {GroupScope="nat-foreign"}}}}).Status==DeliveryStatus.PermanentFailure && snsUnknown.Sns.Requests.Count==calls);
await d.Send(fixtures["recovered"]);var resolved=d.Effects.Single(x=>x.Intent?.Kind==EffectKind.ResolveIncident);d.Dispatch([resolved.Id]);Check("explicit recovery policy publishes a recovery notice",d.Sns.Requests.Count==2 && d.Sns.Requests.Last().Message.Contains("ResolveIncident"));
// Known SNS acceptance followed by an uncertain persistence ACK can legitimately duplicate on retry.
var receiptLost=new Rig();await receiptLost.Send(fixtures["failed"]);var noticeId=receiptLost.Effects.First(x=>x.Intent?.Kind==EffectKind.EscalateIncident).Id;
receiptLost.Sns.AfterPublish=()=>{receiptLost.Ddb.Inner.WriteFailure=new TimeoutException();receiptLost.Sns.AfterPublish=null;};
var lostReceipt=receiptLost.Dispatch([noticeId]);
Check("SNS acceptance without persisted completion is not confirmed",lostReceipt[0].Completion==CompletionStatus.Unknown && receiptLost.Store.ReadEffect(noticeId)!.Status==OutboxStatus.Claimed);
receiptLost.Now=receiptLost.Now.AddSeconds(31);receiptLost.Dispatch([noticeId]);
Check("retry after lost completion may publish duplicate same effect",receiptLost.Sns.Requests.Count==2 && receiptLost.Sns.Requests.Select(x=>x.Message).Distinct().Count()==1 && receiptLost.Store.ReadEffect(noticeId)!.Status==OutboxStatus.Confirmed);
var bounded=new Rig();await bounded.Send(fixtures["failed"]);var boundedId=bounded.Effects.First(x=>x.Intent?.Kind==EffectKind.EscalateIncident).Id;
for(var attempt=0;attempt<4;attempt++){bounded.Sns.Failure=new TimeoutException();bounded.Dispatch([boundedId]);bounded.Now=bounded.Now.AddSeconds(11);}
Check("unknown SNS retries stop at original durable attempt budget",bounded.Sns.Requests.Count==3 && bounded.Store.ReadEffect(boundedId)!.Status==OutboxStatus.PermanentFailure);
using(var expires=ManagedRuntime.Budget(r.Context("ingest"),TimeSpan.Zero))Check("trial expiry caps invocation cancellation",expires.IsCancellationRequested);
var poison=new Rig();var writesBefore=poison.Ddb.Inner.Writes.Count;
Check("NAT payload field rejected by actual managed ingress",(await poison.Send(Change(fixtures["failed"],"Nat",JsonValue.Create("nat-foreign")))).BatchItemFailures.Count==1 && poison.Ddb.Inner.Writes.Count==writesBefore);
var env=Rig.Environment(r.Settings);var read=BackupSettings.Read(env.GetValueOrDefault);Check("explicit region1 settings read",read.Region=="us-east-1");
env["AWS_REGION"]="us-east-2";await Reject("actual region mismatch fails closed",()=>Task.Run(()=>BackupSettings.Read(env.GetValueOrDefault)));
var region2=r.Settings with {Region="us-east-2"};region2.Validate();Check("region configurable without changing external account",region2.QueueArn.Contains(":us-east-2:000000000000:"));
env=Rig.Environment(r.Settings);env.Remove("SENTINEL_AUDIT_SECONDS");await Reject("missing retention not inferred",()=>Task.Run(()=>BackupSettings.Read(env.GetValueOrDefault)));
env=Rig.Environment(r.Settings);env["AWS_PROFILE"]="unusable-local-profile";await Reject("profile fallback refused without credential read",()=>Task.Run(()=>BackupSettings.Read(env.GetValueOrDefault)));
await Reject("invalid dispatch IDs refused before SDK writes",()=>Task.Run(()=>d.Dispatch(["untrusted"])));
if(Environment.GetEnvironmentVariable("ECS_MAIL_EXAMPLES_DIR") is {Length:>0} examples) {
 Directory.CreateDirectory(examples);
 File.WriteAllText(Path.Combine(examples,"failed.txt"),d.Sns.Requests[0].Subject+"\n\n"+d.Sns.Requests[0].Message+"\n");
 File.WriteAllText(Path.Combine(examples,"recovery.txt"),d.Sns.Requests[1].Subject+"\n\n"+d.Sns.Requests[1].Message+"\n");
 File.WriteAllText(Path.Combine(examples,"structured-evidence.json"),d.Sns.Requests[0].MessageAttributes["BackupEvidence"].StringValue+"\n");
}

// Real observer admission is opt-in; neither direction can relabel replay as a genuine check.
var real=new Rig();real.Settings=real.Settings with {Mode="observer-check"};real.Restart();
Check("real observer mode rejects synthetic replay",(await real.Send(fixtures["failed"])).BatchItemFailures.Count==1 && real.Ddb.Inner.Rows.Count==0);
string ActualCheck(string body)=>Change(Change(body,"Evaluation",JsonValue.Create("CHECK_COMMAND_RESULT")),"CheckInvoked",JsonValue.Create(true));
Check("explicit real observer mode accepts checked receipt",(await real.Send(ActualCheck(fixtures["failed"]))).BatchItemFailures.Count==0 && real.Head.State==IncidentState.ESCALATED);
real.Dispatch([real.Effects.Single(x=>x.Intent?.Kind==EffectKind.EscalateIncident).Id]);
Check("real observer notice is not mislabeled synthetic",!real.Sns.Requests[0].Subject.Contains("PRUEBA") && real.Sns.Requests[0].Message.StartsWith("OBSERVACIÓN DE BACKUP") && !DomainJson.Deserialize<BackupNoticeEvidence>(real.Sns.Requests[0].MessageAttributes["BackupEvidence"].StringValue).SyntheticTrial);
var realEnv=Rig.Environment(real.Settings);realEnv["SENTINEL_MODE"]="observer-check";
Check("real observer mode survives explicit settings read",BackupSettings.Read(realEnv.GetValueOrDefault).Mode=="observer-check");
realEnv["SENTINEL_MODE"]="auto";await Reject("unknown runtime mode fails closed",()=>Task.Run(()=>BackupSettings.Read(realEnv.GetValueOrDefault)));
await Reject("real notice opt-in cannot relabel synthetic evidence",()=>Task.Run(()=>BackupNoticeText.Format(structured,"LAST_ATTEMPT_FAILED",real.Now,true)));
var activeReconcile=new Rig();await activeReconcile.Send(fixtures["failed"]);activeReconcile.Now=activeReconcile.Now.AddSeconds(61);
var activeProbeIds=activeReconcile.Effects.Where(x=>x.Intent?.Kind==EffectKind.RequestFunctionalProbe).Select(x=>x.Id).ToArray();
var tick=activeReconcile.Reconcile();
Check("active functional probe remains unsupported, not successful",tick.UnsupportedActiveProbes>0 && activeProbeIds.All(id=>activeReconcile.Store.ReadEffect(id) is {Status:OutboxStatus.Pending,Attempts:0}));
Check("reconcile discovery and dispatch use invocation cancellation",activeReconcile.Ddb.Tokens.All(x=>x.CanBeCanceled));
var closedReconcile=new Rig();await closedReconcile.Send(fixtures["failed"]);await closedReconcile.Send(fixtures["missing"]);await closedReconcile.Send(fixtures["stale"]);await closedReconcile.Send(fixtures["unknown"]);await closedReconcile.Send(fixtures["recovered"]);closedReconcile.Now=closedReconcile.Now.AddSeconds(121);
string? cursor=null;var pages=0;
do {var page=closedReconcile.Reconcile();cursor=page.Continuation;if(++pages>20)throw new Exception("Unbounded discovery");}while(cursor is not null);
Check("bounded discovery progresses over multiple original directory pages",pages>1);
Check("closed episode reconciles every due original outbox item",closedReconcile.Effects.All(x=>x.Status is OutboxStatus.Confirmed or OutboxStatus.Cancelled));
Check("obsolete probes are cancelled without a probe result",closedReconcile.Effects.Where(x=>x.Intent?.Kind==EffectKind.RequestFunctionalProbe).All(x=>x.Status==OutboxStatus.Cancelled && x.Attempts==0));
Check("late failure notice cancelled after recovery, only recovery sent",closedReconcile.Sns.Requests.Count==1 && closedReconcile.Store.ReadEffect(closedReconcile.Effects.Single(e=>e.Intent?.Kind==EffectKind.EscalateIncident).Id)!.Status==OutboxStatus.Cancelled && DomainJson.Deserialize<BackupNoticeEvidence>(closedReconcile.Sns.Requests[0].MessageAttributes["BackupEvidence"].StringValue).Kind=="ResolveIncident");
// Original physical layout + SDK transactions, one namespaced control item, no new store.
var cpRig=new Rig();var cp=new BackupCursorStore(cpRig.Ddb,cpRig.Settings);
using var cpToken=new CancellationTokenSource();
var cpClaim=cp.Acquire("worker-1",cpRig.Now,cpToken.Token)!;
Check("durable cursor lease prevents simultaneous tick",cp.Acquire("worker-2",cpRig.Now,cpToken.Token) is null);
var nextCursor=Convert.ToBase64String(System.Text.Json.JsonSerializer.SerializeToUtf8Bytes(new Dictionary<string,string>{{"PK",cpRig.Settings.Dynamo.Namespace},{"SK","W#example"}}));
Check("different checkpoint worker cannot release a live lease",!cp.Complete(cpClaim with {Record=cpClaim.Record with {Worker="foreign-worker"}},null,cpRig.Now,cpToken.Token));
Check("cursor commits after known completed page",cp.Complete(cpClaim,nextCursor,cpRig.Now,cpToken.Token));
var cpRestart=new BackupCursorStore(cpRig.Ddb,cpRig.Settings);var restarted=cpRestart.Acquire("worker-2",cpRig.Now,cpToken.Token)!;
Check("cursor survives host reconstruction",restarted.Record.Continuation==nextCursor);
Check("stale cursor owner cannot advance progress",!cp.Complete(cpClaim,null,cpRig.Now,cpToken.Token));
Check("expired cursor owner cannot advance progress",!cpRestart.Complete(restarted,null,cpRig.Now.AddSeconds(30),cpToken.Token));
var afterCrash=cpRestart.Acquire("worker-3",cpRig.Now.AddSeconds(31),cpToken.Token)!;
Check("expired lease retries same unadvanced page",afterCrash.Record.Continuation==nextCursor);
await Reject("foreign persisted cursor cannot be stored",()=>Task.Run(()=>cpRestart.Complete(afterCrash,Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes("{\"PK\":\"foreign\",\"SK\":\"W#x\"}")),cpRig.Now.AddSeconds(31),cpToken.Token)));

// Real upstream watchdog, explicit expected-UP/deadline, real store with SDK doubles.
var wd=new Rig();wd.Settings=wd.Settings with {Mode="observer-check",ObserverDeadlineSeconds=60,ObserverExpectedUp=true};wd.Restart();
wd.Now=wd.Settings.StartsAt.AddSeconds(59);wd.Reconcile();
Check("watchdog waits for explicit telemetry deadline",wd.Store.Read(StorageKeys.Aggregate(wd.Settings.Key)) is null);
wd.Now=wd.Settings.StartsAt.AddMinutes(31);wd.Reconcile();
Check("missing observer becomes UNKNOWN, never backup failure or recovery",wd.Head.State==IncidentState.ESCALATED && wd.Sns.Requests.Single().Message.Contains("OBSERVER_HEARTBEAT_EXPIRED") && !wd.Sns.Requests.Single().Message.Contains("FALLO (FAILED)"));
var watchdogRevision=wd.Head.Revision;wd.Reconcile();
Check("same watchdog window deduplicates original receipt",wd.Head.Revision==watchdogRevision && wd.Sns.Requests.Count==1);
Check("actual UNKNOWN heartbeat is durably ACKed",(await wd.Send(ActualCheck(fixtures["unknown"]))).BatchItemFailures.Count==0);wd.Reconcile();
Check("alive UNKNOWN observer does not heal incident",wd.Head.State==IncidentState.ESCALATED);
Check("actual recovery observation is durably ACKed",(await wd.Send(ActualCheck(fixtures["recovered"]))).BatchItemFailures.Count==0);
Check("watchdog and ingress share one explicit catalog",wd.Head.CatalogVersion==BackupSettings.CatalogVersion);
Check("fresh actual healthy check heals observer-loss incident",wd.Head.State==IncidentState.RESOLVED);
var hb=new BackupHeartbeatStore(wd.Ddb,wd.Settings);var newest=hb.Read(CancellationToken.None)!.ObservedAt;
hb.Touch(newest.AddSeconds(-1),CancellationToken.None);
Check("late observation cannot regress heartbeat",hb.Read(CancellationToken.None)!.ObservedAt==newest);
var maintenanceWd=new Rig();maintenanceWd.Settings=maintenanceWd.Settings with {Mode="observer-check",ObserverDeadlineSeconds=60,ObserverExpectedUp=false};maintenanceWd.Restart();maintenanceWd.Reconcile();
Check("expected-down watchdog is disabled without fake success",maintenanceWd.Store.Read(StorageKeys.Aggregate(maintenanceWd.Settings.Key)) is null);
var forgedWd=new Rig();forgedWd.Settings=forgedWd.Settings with {Mode="observer-check",ObserverDeadlineSeconds=60,ObserverExpectedUp=true};forgedWd.Restart();
Check("external sender cannot forge trusted watchdog source",(await forgedWd.Send(Change(ActualCheck(fixtures["failed"]),"Source",JsonValue.Create(Ecs.Backup.Sentinel.BackupIncidentPolicy.WatchdogProducer)))).BatchItemFailures.Count==1 && forgedWd.Ddb.Inner.Rows.Count==0);

var emptyReconcile=new Rig();Check("empty directory has no external effects",emptyReconcile.Reconcile().Results.Length==0 && emptyReconcile.Sns.Requests.Count==0);
await Reject("foreign discovery cursor refused",()=>Task.Run(()=>emptyReconcile.Reconcile(Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes("{\"PK\":\"foreign\",\"SK\":\"W#a\"}")))));

Console.WriteLine(DomainJson.Serialize(new {status="PASS",tests=cases.Count,cases,persistence="ORIGINAL_DYNAMOSTORE_WITH_UPSTREAM_OFFLINE_SDK_DOUBLE",archive="ORIGINAL_S3_ADAPTER_WITH_UPSTREAM_OFFLINE_SDK_DOUBLE",notification="SNS_PUBLISH_SDK_DOUBLE_ONLY",emailSent=false,awsCalls=0,natProvidersConnected=false}));

sealed class Rig {
 public DateTimeOffset Now=DateTimeOffset.Parse("2026-10-23T16:59:59Z");
 public BackupSettings Settings=new("ecs-sentinel-test1","000000000000","us-east-1","ecs-backup-trial","sandbox","ecs-sentinel-test1","sql-backup-test",new("sql-backup","dev-synthetic","backup-health"),"developer",TimeSpan.FromMinutes(5),TimeSpan.FromMinutes(30),TimeSpan.FromMinutes(1),TimeSpan.Zero,
  new StorageLimits(DedupRetention:TimeSpan.FromDays(1),MaxSignalAge:TimeSpan.FromDays(1),AuditRetention:TimeSpan.FromDays(1),EffectRetention:TimeSpan.FromDays(1)),"ECS Test","EscalationAndRecovery",DateTimeOffset.Parse("2026-10-23T16:00:00Z"),DateTimeOffset.Parse("2026-10-24T16:00:00Z"));
 public readonly DdbDouble Ddb=new();public readonly OfflineS3 S3=new();public readonly SnsDouble Sns=new();public IngestFunction Ingest=null!;
 public Rig() {Ddb.Inner.BeforeWrite=null;Ddb.Inner.StaleGsiItem=null;Ddb.Inner.HideGsi=false;Ddb.Inner.EmptyFirstPage=false;S3.NextGetFailure=null;Restart();}
 public void Restart()=>Ingest=new(()=>Settings,_=>new(Ddb,S3,Sns),()=>Now);
 public DynamoStore Store=>new(Ddb.Inner,Settings.Dynamo,Settings.Storage);
 public Incident Head=>Store.Read(StorageKeys.Aggregate(Settings.Key))!.Head;
 public OutboxEntry[] Effects=>Ddb.Inner.Rows.Values.Where(x=>x["SK"].S.StartsWith("O#")).Select(PhysicalLayout.Payload<OutboxEntry>).ToArray();
 public SQSEvent Batch(string body)=>new(){Records=[new(){MessageId="message",Body=body,EventSource="aws:sqs",EventSourceArn=Settings.QueueArn}]};
 public async Task<SQSBatchResponse> Send(string body) {var at=DateTimeOffset.Parse(JsonNode.Parse(body)!["ObservedUtc"]!.GetValue<string>()).AddSeconds(1);if(at>Now)Now=at;return await Ingest.Handler(Batch(body),Context("ingest"));}
 public Context Context(string component,TimeSpan? remaining=null)=>new(Settings.FunctionArn(component),remaining??TimeSpan.FromSeconds(30));
 public DispatchResult[] Dispatch(string[] ids)=>new DispatchFunction(()=>Settings,_=>new(Ddb,S3,Sns),()=>Now).Handler(new(ids),Context("dispatch"));
 public BackupReconcileResult Reconcile(string? cursor=null)=>new DispatchFunction(()=>Settings,_=>new(Ddb,S3,Sns),()=>Now).Reconcile(new(cursor),Context("dispatch"));
 public static Dictionary<string,string?> Environment(BackupSettings c)=>new(){["AWS_REGION"]=c.Region,["SENTINEL_REGION"]=c.Region,["SENTINEL_MODE"]="synthetic-trial",["SENTINEL_RUN_ID"]=c.RunId,["SENTINEL_ACCOUNT"]=c.Account,["SENTINEL_PROJECT"]=c.Project,["SENTINEL_CONSUMER"]=c.Consumer,["SENTINEL_SUBJECT"]=c.Subject,["SENTINEL_SERVICE"]=c.Key.Service,["SENTINEL_SCOPE"]=c.Key.Scope,["SENTINEL_FAILURE_SIGNATURE"]=c.Key.FailureSignature,["SENTINEL_OWNER"]=c.Owner,["SENTINEL_EVIDENCE_SECONDS"]="300",["SENTINEL_BUDGET_SECONDS"]="1800",["SENTINEL_CHECK_SECONDS"]="60",["SENTINEL_HOLD_SECONDS"]="0",["SENTINEL_DEDUP_SECONDS"]="86400",["SENTINEL_SIGNAL_AGE_SECONDS"]="86400",["SENTINEL_AUDIT_SECONDS"]="86400",["SENTINEL_EFFECT_SECONDS"]="86400",["SENTINEL_SENDER_LABEL"]=c.SenderLabel,["SENTINEL_NOTIFICATION_MODE"]=c.NotificationMode,["SENTINEL_STARTS_AT"]="2026-10-23T16:00:00Z",["SENTINEL_EXPIRES_AT"]="2026-10-24T16:00:00Z",["SENTINEL_QUEUE_ARN"]=c.QueueArn,["SENTINEL_TABLE"]=c.Dynamo.Table,["SENTINEL_TOPIC_ARN"]=c.TopicArn,["SENTINEL_BUCKET"]=c.Archive.Bucket,["SENTINEL_NAMESPACE"]=c.Dynamo.Namespace,["SENTINEL_ARCHIVE_PREFIX"]=c.Archive.Prefix};
}
// Original emulator insists on TOTAL for GetItem; production scoped proxy requests INDEXES.
// This test-only shim normalizes that accounting flag; request content/transactions stay original.
sealed class DdbDouble : AmazonDynamoDBClient {
 public readonly OfflineDynamo Inner=new();public readonly List<CancellationToken> Tokens=[];
 public DdbDouble():base(new AnonymousAWSCredentials(),new AmazonDynamoDBConfig{RegionEndpoint=RegionEndpoint.USEast1,MaxErrorRetry=0}) {}
 void Observe(CancellationToken t){t.ThrowIfCancellationRequested();Tokens.Add(t);}
 public override Task<GetItemResponse> GetItemAsync(GetItemRequest r,CancellationToken ct=default){Observe(ct);r.ReturnConsumedCapacity=ReturnConsumedCapacity.TOTAL;return Inner.GetItemAsync(r,ct);}
 public override Task<TransactGetItemsResponse> TransactGetItemsAsync(TransactGetItemsRequest r,CancellationToken ct=default){Observe(ct);return Inner.TransactGetItemsAsync(r,ct);}
 public override Task<TransactWriteItemsResponse> TransactWriteItemsAsync(TransactWriteItemsRequest r,CancellationToken ct=default){Observe(ct);return Inner.TransactWriteItemsAsync(r,ct);}
 public override Task<QueryResponse> QueryAsync(QueryRequest r,CancellationToken ct=default){Observe(ct);return Inner.QueryAsync(r,ct);}
}
sealed class SnsDouble : AmazonSimpleNotificationServiceClient {
 public readonly List<PublishRequest> Requests=[];public Action? AfterPublish;public Exception? Failure;public string MessageId="synthetic-message-id";
 public SnsDouble():base(new AnonymousAWSCredentials(),new AmazonSimpleNotificationServiceConfig{RegionEndpoint=RegionEndpoint.USEast1,MaxErrorRetry=0}) {}
 public override Task<PublishResponse> PublishAsync(PublishRequest r,CancellationToken ct=default){ct.ThrowIfCancellationRequested();Requests.Add(r);var e=Failure;Failure=null;if(e is not null)throw e;AfterPublish?.Invoke();return Task.FromResult(new PublishResponse {HttpStatusCode=HttpStatusCode.OK,MessageId=MessageId});}
}
sealed record Context(string InvokedFunctionArn,TimeSpan RemainingTime) : ILambdaContext {
 public string AwsRequestId=>"synthetic-invocation";public IClientContext ClientContext=>null!;public string FunctionName=>"synthetic";public string FunctionVersion=>"$LATEST";public ICognitoIdentity Identity=>null!;
 public ILambdaLogger Logger=>new Logger();public string LogGroupName=>"synthetic";public string LogStreamName=>"synthetic";public int MemoryLimitInMB=>512;public string TenantId=>"synthetic";public string TraceId=>"synthetic";
 public ILambdaSerializer Serializer=>new Amazon.Lambda.Serialization.SystemTextJson.DefaultLambdaJsonSerializer();
}
sealed class Logger : ILambdaLogger {public void Log(string message){}public void LogLine(string message){}}
