using Ecs.Backup.Sentinel;
using Sentinel.Core;
using Sentinel.Application;
using Sentinel.Ingestion;
using Sentinel.Persistence.Fakes;
using System.Collections.Immutable;
using System.Text.Json.Nodes;

var fixtures=Directory.GetFiles(args.Single(),"*.json").ToDictionary(p=>Path.GetFileNameWithoutExtension(p)!,p=>File.ReadAllText(p));
var now=DateTimeOffset.Parse("2026-10-23T18:00:00Z");
var key=new CorrelationKey("sql-backup","dev-synthetic","backup-health");
var options=new IngestionOptions("000000000000","us-east-1","ecs-demo","local",[ObserverNormalizer.Producer],[key]);
var normalizer=new ObserverNormalizer("sql-backup-test",key);
var db=new MemoryDatabase();var store=new TransactionalMemoryStore(db,StorageLimits.Default);
// Existing upstream policy requires NAT-shaped settings. Test-only placeholders, never bindings/resources/probes.
var policy=new RecoveryPolicy(new("ecs-backup-ingress-probe-v1"),TimeSpan.FromMinutes(30),TimeSpan.FromMinutes(5),
    TimeSpan.FromMinutes(1),TimeSpan.Zero,TimeSpan.Zero,TimeSpan.FromMinutes(1),1,TimeSpan.Zero,
    new(1,"not-applicable","not-applicable","not-applicable",["not-applicable"],["not-applicable"]),"developer",null);
IngestionProcessor Processor()=>new(normalizer,options,_=>new(new SignalProcessor(store,new IncidentReducer(new UnqualifiedBackupRecovery()),StorageLimits.Default)),_=>policy);
var processor=Processor();var ingress=new BackupIngress(normalizer,processor);
var tests=new List<string>();
void Check(string name,bool value) { if(!value) throw new Exception("FAILED: "+name);tests.Add(name); }
string Change(string body,string field,JsonNode? value) { var n=JsonNode.Parse(body)!.AsObject();n[field]=value;return n.ToJsonString(); }
MessageResult Send(string fixture)=>ingress.Process(fixtures[fixture],fixture,now)??throw new Exception("unexpected suppression");
foreach(var status in new[]{"failed","missing","stale"}) {
 var r=Send(status);Check(status+" real ingress commit",r.Status==ProcessingStatus.Committed && !r.Retry && r.Signal!.Kind==SignalKind.Failure);
 Check(status+" audit metadata",store.History(StorageKeys.Aggregate(key)).Last().SourceMetadata!["backupStatus"]==status.ToUpperInvariant());
}
var effects=store.Effects(StorageKeys.Aggregate(key)).Length;var revision=store.Read(StorageKeys.Aggregate(key))!.Head.Revision;
now=now.AddSeconds(1);processor=Processor();ingress=new(normalizer,processor);
var duplicate=Send("stale");Check("redelivery after processor restart dedup",duplicate.Status==ProcessingStatus.Duplicate && store.Read(StorageKeys.Aggregate(key))!.Head.Revision==revision && store.Effects(StorageKeys.Aggregate(key)).Length==effects);
Check("unchanged candidate suppressed before ingestion",ingress.Process(fixtures["unchanged"],"suppressed",now) is null && store.Read(StorageKeys.Aggregate(key))!.Head.Revision==revision);
Check("baseline healthy suppressed",ingress.Process(fixtures["baseline"],"baseline",now) is null);
Check("maintenance suppressed",ingress.Process(fixtures["maintenance"],"maintenance",now) is null);
var unknown=Send("unknown");Check("unknown is telemetry loss, never missing",unknown.Signal!.Kind==SignalKind.TelemetryLost && store.History(StorageKeys.Aggregate(key)).Last().SourceMetadata!["backupStatus"]=="UNKNOWN");
var recovery=Send("recovered");Check("recovery candidate applied and audited",recovery.Status==ProcessingStatus.Committed && recovery.Signal!.Kind==SignalKind.Evidence && store.History(StorageKeys.Aggregate(key)).Last().SourceMetadata!["backupStatus"]=="HEALTHY");
Check("backup recovery cannot certify NAT or close incident",store.Read(StorageKeys.Aggregate(key))!.Head.State==IncidentState.RECOVERING && recovery.Reduction!.Decision.Assessment!.Status==RecoveryStatus.InsufficientEvidence && !recovery.Reduction.Decision.Effects.Any(e=>e.Kind==EffectKind.ResolveIncident));
Check("real upstream pending archive and incident outbox",store.Effects(StorageKeys.Aggregate(key)).Any(e=>e.Kind==WorkKind.ArchiveDecision) && store.Effects(StorageKeys.Aggregate(key)).Any(e=>e.Intent?.Kind==EffectKind.OpenIncident) && store.Effects(StorageKeys.Aggregate(key)).All(e=>e.Status==OutboxStatus.Pending));
var before=store.History(StorageKeys.Aggregate(key)).Length;
foreach(var (name,field,value) in new (string,string,JsonNode?)[]{("wrong subject","Subject",JsonValue.Create("other")),("secret field","Password",JsonValue.Create("synthetic-private")),("false live claim","SentinelIntegrated",JsonValue.Create(true)),("false remediation","RemediationAllowed",JsonValue.Create(true)),("wrong pair","Code",JsonValue.Create("NO_REMOTE_COMMIT")),("future time","ObservedUtc",JsonValue.Create("2099-01-01T00:00:00Z")),("wrong emit type","Emit",JsonValue.Create("true")),("invented transport","Delivery",JsonValue.Create("EMAIL"))}) {
 var r=ingress.Process(Change(fixtures["failed"],field,value),name,now);Check(name+" refused before write",r is {Retry:true,Failure:FailureClass.Poison} && store.History(StorageKeys.Aggregate(key)).Length==before);
 Check(name+" sanitized failure",r!.Code=="backup-observer-contract" && !DomainJson.Serialize(r).Contains("synthetic-private"));
}
var dupe=fixtures["failed"].Replace("\"SchemaVersion\":1","\"SchemaVersion\":1,\"SchemaVersion\":1");
Check("duplicate JSON key refused",normalizer.Normalize(dupe,options,now).Status==Admission.Malformed);
Check("oversized input refused",normalizer.Normalize(new string('x',65537),options,now).Status==Admission.Malformed);
Check("foreign catalog refused",normalizer.Normalize(fixtures["failed"],options with {Resources=[new("other","other","other")]},now).Status==Admission.Malformed);
Check("no synthetic EventBridge wrapper",!fixtures["failed"].Contains("sentinel.synthetic") && !fixtures["failed"].Contains("aws.cloudwatch"));
Console.WriteLine(DomainJson.Serialize(new {Status="PASS",Tests=tests.Count,Cases=tests,Persistence="UPSTREAM_MEMORY_FAKE",Transport="IN_PROCESS",EmailSent=false,CloudCalls=0,BackupRecoveryPolicyQualified=false}));

// Deliberate consumer-side guard: actual ingress/reducer/store integration does not invent backup recovery semantics.
sealed class UnqualifiedBackupRecovery : IRecoveryEvaluator {
 public RecoveryAssessment Assess(Incident incident,RecoveryPolicy policy,EvaluationContext context)=>new(RecoveryStatus.InsufficientEvidence,
   [new(ReasonCode.MissingEvidence,"backup.policy.pending","Backup-specific recovery evaluation is not implemented upstream; no NAT facts fabricated.",[])],[],false);
}
