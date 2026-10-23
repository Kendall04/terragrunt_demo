using Ecs.Backup.Sentinel;
using Sentinel.Core;
using Sentinel.Application;
using Sentinel.Ingestion;
using Sentinel.Persistence.Fakes;
using Sentinel.Observability;
using System.Text.Json.Nodes;

var fixtures=Directory.GetFiles(args.Single(),"*.json").ToDictionary(p=>Path.GetFileNameWithoutExtension(p)!,File.ReadAllText);
var cases=new List<string>();
void Check(string name,bool value) { if(!value)throw new Exception("FAILED: "+name);cases.Add(name); }
string Change(string body,string field,JsonNode? value) {var n=JsonNode.Parse(body)!.AsObject();n[field]=value;return n.ToJsonString();}
var r=new Rig();
var opened=r.Send(fixtures["failed"])!;
Check("FAILED opens real escalated backup incident",opened.Status==ProcessingStatus.Committed && r.Head.State==IncidentState.ESCALATED && opened.Reduction!.Decision.Assessment!.Status==RecoveryStatus.Failed);
var incident=r.Head.Id;var revision=r.Head.Revision;var count=r.Effects.Length;
Check("persistent unchanged failure suppressed",r.Send(fixtures["failed-unchanged"]) is null && r.Head.Revision==revision && r.Effects.Length==count);
var reminder=r.Send(fixtures["failed-reminder"])!;
Check("reminder retains same incident and episode",reminder.Status==ProcessingStatus.Committed && r.Head.Id==incident && r.Head.Epoch==1);
Check("persistent failure has one escalation intent",r.Effects.Count(e=>e.Intent?.Kind==EffectKind.EscalateIncident)==1);
foreach(var status in new[]{"missing","stale"}) {
 var outcome=r.Send(fixtures[status])!;
 Check(status+" real failure application",outcome.Status==ProcessingStatus.Committed && outcome.Signal!.Kind==SignalKind.Failure && r.Head.Id==incident);
 Check(status+" safe audit metadata",r.History.Last().SourceMetadata!["backupStatus"]==status.ToUpperInvariant());
}
revision=r.Head.Revision;count=r.Effects.Length;r.Restart();r.Now=r.Now.AddSeconds(1);
Check("redelivery after processor reconstruction deduplicates",r.Send(fixtures["stale"])!.Status==ProcessingStatus.Duplicate && r.Head.Revision==revision && r.Effects.Length==count);
Check("unchanged stale suppressed",r.Send(fixtures["unchanged"]) is null && r.Head.Revision==revision);
var unknown=r.Send(fixtures["unknown"])!;
Check("UNKNOWN is telemetry loss not missing",unknown.Signal!.Kind==SignalKind.TelemetryLost && r.History.Last().SourceMetadata!["backupStatus"]=="UNKNOWN");
Check("UNKNOWN cannot clear persistent incident",r.Head.State==IncidentState.ESCALATED && unknown.Reduction!.Decision.Assessment!.Status==RecoveryStatus.InsufficientEvidence);
var recovered=r.Send(fixtures["recovered"])!;
Check("fresh healthy observation resolves escalated backup incident",recovered.Status==ProcessingStatus.Committed && r.Head.State==IncidentState.RESOLVED && recovered.Reduction!.Decision.Assessment!.Status==RecoveryStatus.Successful);
Check("resolution intent emitted once",r.Effects.Count(e=>e.Intent?.Kind==EffectKind.ResolveIncident)==1);
revision=r.Head.Revision;count=r.Effects.Length;
Check("recovery redelivery deduplicates",r.Send(fixtures["recovered"])!.Status==ProcessingStatus.Duplicate && r.Head.Revision==revision && r.Effects.Length==count);
Check("healthy unchanged after closed incident suppressed",r.Send(fixtures["baseline"]) is null && r.Head.Revision==revision);
Check("maintenance does not mutate closed incident",r.Send(fixtures["maintenance"]) is null && r.Head.Revision==revision);
var recur=r.Send(fixtures["recurrence"])!;
Check("later failure opens new incident epoch",recur.Status==ProcessingStatus.Committed && r.Head.State==IncidentState.ESCALATED && r.Head.Epoch==2 && r.Head.Id!=incident);
Check("recurrence has exactly one new escalation",r.Effects.Count(e=>e.Intent?.Kind==EffectKind.EscalateIncident)==2);
revision=r.Head.Revision;r.Restart();
Check("old recovery replay retains original audit epoch and deduplicates",r.Send(fixtures["recovered"])!.Status==ProcessingStatus.Duplicate && r.Head.Epoch==2 && r.Head.Revision==revision && r.Head.State==IncidentState.ESCALATED);
Check("new episode recovery uses current epoch",r.Send(fixtures["recovered2"])!.Status==ProcessingStatus.Committed && r.Head.State==IncidentState.RESOLVED && r.Head.Epoch==2);
Check("all actual outbox work remains pending no delivery",r.Effects.All(e=>e.Status==OutboxStatus.Pending) && r.Effects.Any(e=>e.Kind==WorkKind.ArchiveDecision));
Check("no NAT mutation or NAT-targeted probe",r.Effects.All(e=>e.Intent?.Kind!=EffectKind.RequestFunctionalProbe || e.Intent.Target==r.Key.Scope));
Check("no capacity EIP route or egres facts fabricated",r.History.SelectMany(a=>a.Signal.Evidence).All(e=>e.Facts.HealthyCapacity is null && e.Facts.EipIdentity is null && e.Facts.RouteInstance is null && e.Facts.HttpsSucceeded is null));

var telemetry=new Rig();telemetry.Send(fixtures["unknown"]);
Check("UNKNOWN alone opens uncertain incident",telemetry.Head.State==IncidentState.RECOVERING && telemetry.History.Last().Reduction.Decision.Assessment!.Status==RecoveryStatus.InsufficientEvidence);
telemetry.Send(fixtures["recovered"]);
Check("first healthy after uncertainty records AUTO_RECOVERED",telemetry.Head.State==IncidentState.AUTO_RECOVERED);
var confirmation=telemetry.Send(fixtures["baseline"]);
Check("second genuine healthy observation closes uncertainty episode",confirmation?.Status==ProcessingStatus.Committed && telemetry.Head.State==IncidentState.RESOLVED);
revision=telemetry.Head.Revision;
Check("confirmation replay deduplicates after closure",telemetry.Send(fixtures["baseline"])?.Status==ProcessingStatus.Duplicate && telemetry.Head.Revision==revision);

var late=new Rig();late.Send(fixtures["recurrence"]);late.Send(fixtures["recovered"]);
Check("older healthy observation cannot clear a later failure",late.Head.State==IncidentState.ESCALATED && late.History.Last().Reduction.Decision.Assessment!.Status==RecoveryStatus.Failed);
var tied=new Rig();tied.Send(fixtures["failed"]);
var healthyTie=Change(Change(fixtures["recovered"],"ObservedUtc",JsonValue.Create("2026-10-23T17:00:00Z")),"LastSuccessUtc",JsonValue.Create("2026-10-23T17:00:00Z"));
tied.Send(healthyTie);
Check("same-time contradictory health cannot recover",tied.Head.State==IncidentState.ESCALATED);
var expired=new Rig();expired.Send(fixtures["failed"]);expired.Now=DateTimeOffset.Parse("2026-10-23T17:14:00Z");expired.Send(fixtures["recovered"]);
Check("expired healthy observation cannot recover",expired.Head.State==IncidentState.ESCALATED && expired.History.Last().Reduction.Decision.Assessment!.Status==RecoveryStatus.InsufficientEvidence);
var lost=new Rig();lost.Send(fixtures["unknown"]);
var unknownLater=Change(Change(fixtures["unknown"],"ObservedUtc",JsonValue.Create("2026-10-23T17:40:00Z")),"Reason",JsonValue.Create("REMINDER_DUE"));lost.Send(unknownLater);
Check("persistent UNKNOWN overdue escalates without fabricated health",lost.Head.State==IncidentState.ESCALATED && lost.History.Last().Reduction.Decision.Assessment!.Status==RecoveryStatus.Overdue);
var hydrated=OperationalProjection.Hydrate(late.Store.Read(StorageKeys.Aggregate(late.Key))!);
var unrelated=new RecoveryEvidence("unrelated",EvidenceKind.Readiness,late.Key.Scope,ObserverNormalizer.Producer,hydrated.Epoch,"nat-generation",late.Now,late.Now,late.Now.AddMinutes(1),new(){Ready=true,HttpsSucceeded=true});
var assessment=new BackupIncidentPolicy(late.Key).Assess(hydrated with {Evidence=[unrelated]},late.Policy,new(late.Now,"test",[],[]));
Check("unrelated NAT readiness is not backup recovery",assessment.Status==RecoveryStatus.InsufficientEvidence);
var wrongEpoch=unrelated with {Epoch=hydrated.Epoch+1,Generation="backup-health/HEALTHY"};
Check("wrong epoch evidence is not recovery",new BackupIncidentPolicy(late.Key).Assess(hydrated with {Evidence=[wrongEpoch]},late.Policy,new(late.Now,"test",[],[])).Status==RecoveryStatus.InsufficientEvidence);

// Poisoned legacy fields must fail before any incident/audit/outbox transaction.
var poisoned=new Rig(p=>p with {Nat=p.Nat with {GroupScope="nat-asg-a",ExpectedEipIdentity="eip-nat-a",RouteScopes=["nat-route-a"]}});
var blocked=poisoned.Send(fixtures["failed"]);
Check("legacy NAT bindings rejected before backup commit",blocked is {Retry:true,Failure:FailureClass.Security,Code:"backup-policy-scope"});
Check("poisoned policy enqueues no NAT or other effects",poisoned.Store.Read(StorageKeys.Aggregate(poisoned.Key)) is null && poisoned.Effects.IsEmpty && poisoned.History.IsEmpty);

// A real NAT-only catalog must reject a committed backup read-probe before touching its provider.
var route=new Rig();route.Send(fixtures["failed"]);
var probe=route.Effects.First(e=>e.Intent?.Kind==EffectKind.RequestFunctionalProbe);route.Now=probe.DueAt.AddSeconds(1);
var natKey=new CorrelationKey("nat-service","zone-a","nat-egress");
var natPolicy=route.Policy with {Version=new("nat-negative-v1"),ProbeSpacing=TimeSpan.FromSeconds(1),Nat=new(1,"nat-asg-a","nat-instance-a","eip-nat-a",["nat-route-a"],["nat-automation"])};
var natCatalog=new ServiceCatalog(1,"ecs-backup-observer-v2","000000000000","us-east-1","ecs-demo","local",
 [new("nat-service",natKey,"nat-asg",natPolicy,[new(ResourceKind.CloudWatchAlarm,"arn:aws:cloudwatch:us-east-1:000000000000:alarm:synthetic-nat")],[],"nat-negative-provider",TimeSpan.FromMinutes(1),["RequestFunctionalProbe"])]);
natCatalog.Validate();var trap=new TrapNatProvider();
var natWorker=new RecoveryCheckWorker(route.Store,new SignalProcessor(route.Store,new IncidentReducer(new BackupIncidentPolicy(route.Key)),StorageLimits.Default),natCatalog,
 new Dictionary<string,IEvidenceProvider>{{"nat-negative-provider",trap}},DispatchPolicy.Default,()=>route.Now);
var denied=natWorker.Dispatch(probe.Id,"negative-routing-test");
Check("real NAT catalog rejects backup correlation key",denied.Detail=="Catalog mismatch." && route.Store.ReadEffect(probe.Id)!.Status==OutboxStatus.PermanentFailure);
Check("rejected NAT route never invokes provider",trap.Calls==0);

var before=r.History.Length;
foreach(var (name,field,value) in new (string,string,JsonNode?)[]{("wrong subject","Subject",JsonValue.Create("other")),("secret field","Password",JsonValue.Create("synthetic-private")),("false live claim","SentinelIntegrated",JsonValue.Create(true)),("false remediation","RemediationAllowed",JsonValue.Create(true)),("wrong pair","Code",JsonValue.Create("NO_REMOTE_COMMIT")),("future time","ObservedUtc",JsonValue.Create("2099-01-01T00:00:00Z")),("wrong emit type","Emit",JsonValue.Create("true")),("invented transport","Delivery",JsonValue.Create("EMAIL"))}) {
 var result=r.Send(Change(fixtures["failed"],field,value),false);
 Check(name+" refused before write",result is {Retry:true,Failure:FailureClass.Poison} && r.History.Length==before);
 Check(name+" sanitized failure",result!.Code=="backup-observer-contract" && !DomainJson.Serialize(result).Contains("synthetic-private"));
}
var duplicateJson=fixtures["failed"].Replace("\"SchemaVersion\":1","\"SchemaVersion\":1,\"SchemaVersion\":1");
Check("duplicate JSON field refused",r.Normalizer.Normalize(duplicateJson,r.Options,r.Now).Status==Admission.Malformed);
Check("oversized input refused",r.Normalizer.Normalize(new string('x',65537),r.Options,r.Now).Status==Admission.Malformed);
Check("foreign catalog refused",r.Normalizer.Normalize(fixtures["failed"],r.Options with {Resources=[new("foreign","foreign","foreign")]},r.Now).Status==Admission.Malformed);
Check("no synthetic EventBridge or AWS source impersonation",!fixtures["failed"].Contains("sentinel.synthetic") && !fixtures["failed"].Contains("aws.cloudwatch"));
Console.WriteLine(DomainJson.Serialize(new {Status="PASS",Tests=cases.Count,Cases=cases,Persistence="UPSTREAM_MEMORY_FAKE",Transport="IN_PROCESS",EmailSent=false,CloudCalls=0,BackupObserverPolicyQualifiedLocally=true,DatabaseRecoveryQualified=false,EffectsExecuted=0}));

sealed class Rig {
 public readonly CorrelationKey Key=new("sql-backup","dev-synthetic","backup-health");
 public readonly MemoryDatabase Database=new();
 public readonly RecoveryPolicy Policy;
 public readonly IngestionOptions Options;
 public DateTimeOffset Now=DateTimeOffset.Parse("2026-10-23T16:59:59Z");
 public TransactionalMemoryStore Store=null!;
 public ObserverNormalizer Normalizer=null!;
 private BackupIngress ingress=null!;
 public Rig(Func<RecoveryPolicy,RecoveryPolicy>? alter=null) {
  Policy=BackupIncidentPolicy.Create(Key,TimeSpan.FromMinutes(5),TimeSpan.FromMinutes(30),TimeSpan.FromMinutes(1),TimeSpan.Zero,"developer");
  if(alter is not null)Policy=alter(Policy);
  Options=new("000000000000","us-east-1","ecs-demo","local",[ObserverNormalizer.Producer],[Key]);Restart();
 }
 public void Restart() {
  Store=new(Database,StorageLimits.Default);Normalizer=new("sql-backup-test",Key,Store,Policy);
  var processor=new IngestionProcessor(Normalizer,Options,_=>new(new SignalProcessor(Store,new IncidentReducer(new BackupIncidentPolicy(Key)),StorageLimits.Default)),_=>Policy,
    contexts:now=>new(now,"ecs-backup-observer-v2",[],[]));ingress=new(Normalizer,processor);
 }
 public MessageResult? Send(string body,bool advance=true) {
  if(advance) {var observed=DateTimeOffset.Parse(JsonNode.Parse(body)!["ObservedUtc"]!.GetValue<string>()).AddSeconds(1);if(observed>Now)Now=observed;}
  return ingress.Process(body,"local-message",Now);
 }
 public Incident Head=>Store.Read(StorageKeys.Aggregate(Key))!.Head;
 public System.Collections.Immutable.ImmutableArray<AuditRecord> History=>Store.History(StorageKeys.Aggregate(Key));
 public System.Collections.Immutable.ImmutableArray<OutboxEntry> Effects=>Store.Effects(StorageKeys.Aggregate(Key));
}

sealed class TrapNatProvider : IEvidenceProvider {
 public int Calls {get;private set;}
 public EvidenceObservation Observe(EvidenceRequest request,CancellationToken cancellationToken) {Calls++;throw new InvalidOperationException("NAT_PROVIDER_MUST_NOT_RUN");}
}
