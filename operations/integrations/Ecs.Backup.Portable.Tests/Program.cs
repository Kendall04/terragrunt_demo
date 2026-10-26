using System.Text.Json.Nodes;
using System.Collections.Immutable;
using Sentinel.Core;
using Sentinel.Application;
using Sentinel.Ingestion;
using Sentinel.Persistence.Fakes;
using Sentinel.Portable;
var root=args.Single();var cases=new List<string>();
void Check(string n,bool v){if(!v)throw new Exception("FAILED: "+n);cases.Add(n);}
var config=StrictJson.Installation(File.ReadAllText(Path.Combine(root,"sentinel.json")));
var at=DateTimeOffset.Parse("2026-10-26T03:00:00Z");
var backup=config.Monitors.Single(m=>m.Id=="sql-backup");var telemetry=config.Monitors.Single(m=>m.Id=="sql-telemetry");
Check("real upstream validates exactly backup and host telemetry",config.Monitors.Length==2 && backup.Kind=="sql-backup" && telemetry.Kind=="report");
JsonObject[] Entries(string name)=>JsonNode.Parse(File.ReadAllText(Path.Combine(root,name+".json")))!.AsArray().Select(n=>n!.AsObject()).ToArray();
string Envelope(JsonObject entry){return new JsonObject{["id"]="synthetic-envelope",["source"]=entry["Source"]!.GetValue<string>(),["detail-type"]=entry["DetailType"]!.GetValue<string>(),["account"]=config.Account,["region"]=config.Region,["detail"]=JsonNode.Parse(entry["Detail"]!.GetValue<string>())}.ToJsonString();}
var entries=Entries("healthy");var r=new Rig(config,at);
foreach(var m in config.Monitors)Check("original MonitorBootstrap persists expectation "+m.Id,r.Bootstrap(m) is {Status:ProcessingStatus.Committed});
foreach(var entry in entries)Check("real ingress commits projected "+entry["Source"],r.Send(Envelope(entry)) is {Retry:false,Status:ProcessingStatus.Committed});
Check("healthy baseline does not invent a business incident",r.Head(backup).State==IncidentState.MONITORING);
var revision=r.Head(backup).Revision;r.Restart();
Check("real receipt deduplicates after processor restart",r.Send(Envelope(entries[0])) is {Status:ProcessingStatus.Duplicate} && r.Head(backup).Revision==revision);
Check("unchanged heartbeat is separately persisted",r.Store.History(StorageKeys.Aggregate(telemetry.Key)).Length==2);
var lost=new Rig(config,at);foreach(var m in config.Monitors)lost.Bootstrap(m);
lost.Now=at.AddMinutes(11);
Check("bootstrap does not replace still executable overdue work",lost.Bootstrap(backup).Status==ProcessingStatus.Ignored);
var promised=lost.Store.Effects(StorageKeys.Aggregate(backup.Key)).Single(e=>e.Intent?.Kind==EffectKind.ScheduleRecoveryCheck);
var claim=lost.Store.TryClaim(promised.Id,"fixture-terminal-worker",lost.Now,DispatchPolicy.Default)!;
lost.Store.Complete(claim,new(DeliveryStatus.PermanentFailure,"SYNTHETIC_TERMINAL_WORK"),lost.Now,DispatchPolicy.Default);
Check("original bootstrap repairs terminal chain without retrying failed work",lost.Bootstrap(backup).Status==ProcessingStatus.Committed && lost.Store.ReadEffect(promised.Id)!.Status==OutboxStatus.PermanentFailure);
lost.Now=at.AddMinutes(13);lost.Evaluate(backup);
Check("no backup report eventually escalates real monitor",lost.Head(backup).State==IncidentState.ESCALATED);
Check("missing is insufficient evidence not failed SQL",lost.Store.History(StorageKeys.Aggregate(backup.Key)).Last().Reduction.Decision.Assessment!.Status==RecoveryStatus.InsufficientEvidence);
// Each scenario has an independent store and monotonic clock.
var fresh=new Rig(config,at);foreach(var m in config.Monitors)fresh.Bootstrap(m);foreach(var e in entries)fresh.Send(Envelope(e));
fresh.Now=at.AddMinutes(23);fresh.Evaluate(telemetry);fresh.Now=at.AddMinutes(25);fresh.Evaluate(telemetry);
Check("host disappearance escalates telemetry independently",fresh.Head(telemetry).State==IncidentState.ESCALATED && fresh.Head(backup).State==IncidentState.MONITORING);
Check("host absence is UNKNOWN assessment",fresh.Store.History(StorageKeys.Aggregate(telemetry.Key)).Last().Reduction.Decision.Assessment!.Status==RecoveryStatus.InsufficientEvidence);
foreach(var name in new[]{"missing","unknown","failed"}){
 var x=new Rig(config,at);foreach(var m in config.Monitors)x.Bootstrap(m);
 foreach(var e in Entries(name))x.Send(Envelope(e));x.Now=at.AddMinutes(11);x.Evaluate(backup);x.Now=at.AddMinutes(13);x.Evaluate(backup);
 Check(name+" does not resolve or claim confirmed impact",x.Head(backup).State==IncidentState.ESCALATED && !x.Store.History(StorageKeys.Aggregate(backup.Key)).Last().Reduction.Decision.Assessment!.ConfirmedServiceImpact);
}
var stale=new Rig(config,at);foreach(var m in config.Monitors)stale.Bootstrap(m);foreach(var e in Entries("stale"))stale.Send(Envelope(e));
stale.Now=at.AddMinutes(11);stale.Evaluate(backup);
Check("new arrival of old COPY_ONLY backup remains overdue",stale.Head(backup).State==IncidentState.RECOVERING);
var recovered=new Rig(config,at);foreach(var m in config.Monitors)recovered.Bootstrap(m);recovered.Now=at.AddMinutes(13);recovered.Evaluate(backup);recovered.Now=at.AddMinutes(16);recovered.Evaluate(backup);
JsonObject Later(JsonObject entry,DateTimeOffset time,bool renewData){var copy=(JsonObject)entry.DeepClone();var report=JsonNode.Parse(copy["Detail"]!.GetValue<string>())!.AsObject();report["id"]=DomainJson.StableId(report["id"]!.GetValue<string>(),time.ToString("O"));report["observedAt"]=time.ToString("O");if(renewData)report["dataAt"]=time.AddMinutes(-1).ToString("O");copy["Detail"]=report.ToJsonString();return copy;}
recovered.Now=at.AddMinutes(17);recovered.Send(Envelope(Later(Entries("unknown")[1],recovered.Now,true)));
Check("host return does not heal backup incident",recovered.Head(backup).State==IncidentState.ESCALATED);
var valid=Later(entries[0],recovered.Now,true);recovered.Send(Envelope(valid));
Check("fresh valid backup evidence resolves original reducer",recovered.Head(backup).State==IncidentState.RESOLVED);
Check("resolution keeps future supervision scheduled",recovered.Store.Effects(StorageKeys.Aggregate(backup.Key)).Any(e=>e.Intent?.Kind==EffectKind.ScheduleRecoveryCheck && e.Status==OutboxStatus.Pending));
var before=recovered.Head(backup).Revision;recovered.Now=at.AddMinutes(18);recovered.Send(Envelope(entries[0]));
Check("old first delivery cannot replace newer recovery evidence",recovered.Head(backup).State==IncidentState.RESOLVED && recovered.Store.Read(StorageKeys.Aggregate(backup.Key))!.Evidence.Max(e=>e.ObservedAt)==at.AddMinutes(17));
var replayRevision=recovered.Head(backup).Revision;recovered.Send(Envelope(entries[0]));
Check("old delivery retry remains duplicate",recovered.Head(backup).Revision==replayRevision);
foreach(var field in new[]{"producer","resource","generation","backupType"}){
 var report=DomainJson.Deserialize<Report>(entries[0]["Detail"]!.GetValue<string>());
 var altered=field switch{"producer"=>report with{Producer="foreign"},"resource"=>report with{Resource="foreign"},"generation"=>report with{Generation="foreign"},_=>report with{BackupType="log"}};
 var wrong=(JsonObject)entries[0].DeepClone();wrong["Detail"]=DomainJson.Serialize(altered);
 var trial=new Rig(config,at);var result=trial.Send(Envelope(wrong));Check("foreign "+field+" retries without persistence",result.Retry && trial.Store.Read(StorageKeys.Aggregate(backup.Key)) is null);
}
var wrongTenant=JsonNode.Parse(Envelope(entries[0]))!.AsObject();wrongTenant["account"]="000000000000";
Check("foreign account refused by original normalizer",new Rig(config,at).Send(wrongTenant.ToJsonString()).Retry);
var futureReport=Later(entries[0],at.AddMinutes(1),true);Check("future evidence refused",new Rig(config,at).Send(Envelope(futureReport)).Retry);
var bad=new Rig(config,at);var noCall=new CancellationToken(true);Check("cancellation never ACKs absent commit",bad.Send(Envelope(entries[0]),noCall).Retry && bad.Store.Read(StorageKeys.Aggregate(backup.Key)) is null);
Check("maintenance emits no fake heartbeat",Entries("maintenance").Length==0);
Check("no NAT functional probe or provider requested",new[]{r,fresh,stale,recovered}.All(x=>config.Monitors.All(m=>x.Store.Effects(StorageKeys.Aggregate(m.Key)).All(e=>e.Intent?.Kind!=EffectKind.RequestFunctionalProbe))));
Check("outbox is real but no delivery or drain is claimed",recovered.Store.Effects(StorageKeys.Aggregate(backup.Key)).Any(e=>e.Kind==WorkKind.ArchiveDecision) && recovered.Store.Effects(StorageKeys.Aggregate(backup.Key)).All(e=>e.Status==OutboxStatus.Pending));
Console.WriteLine(DomainJson.Serialize(new{Status="PASS",Tests=cases.Count,Cases=cases,Upstream="b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828",Persistence="ORIGINAL_UPSTREAM_MEMORY_FAKE",AwsCalls=0,EmailSent=false,Upstream749Rerun=false}));
sealed class Rig{
 public readonly Installation Config;public readonly MemoryDatabase Db=new();public DateTimeOffset Now;public TransactionalMemoryStore Store=null!;SignalProcessor processor=null!;IngestionProcessor ingress=null!;
 public Rig(Installation c,DateTimeOffset at){Config=c;Now=at;Restart();}
 public void Restart(){Store=new(Db,Config.Storage);processor=new(Store,new IncidentReducer(new NatRecoveryEvaluator()),Config.Storage);var cat=Config.Catalog();var options=new IngestionOptions(Config.Account,Config.Region,Config.Project,Config.Environment,["sql-observer"],Config.Monitors.Select(m=>m.Key).ToImmutableArray());ingress=new(new ReportNormalizer(Config,k=>Store.Read(StorageKeys.Aggregate(k))?.Head.Epoch??1),options,_=>new(processor),k=>cat.Resolve(k).Policy,contexts:cat.Context);}
 public ProcessingResult Bootstrap(MonitorDefinition m)=>MonitorBootstrap.Ensure(m,Store,processor,Config.Catalog(),Now);
 // Explicit timer-input evaluation exercises the real reducer/transaction, not a running worker.
 public ProcessingResult Evaluate(MonitorDefinition m)=>processor.Process(new(1,DomainJson.StableId("synthetic-timer",m.Id,Now.ToString("O")),"timer",m.Key,SignalKind.Evaluate,Now,Now,Now,[]),m.Policy,Config.Catalog().Context(Now));
 public MessageResult Send(string body,CancellationToken token=default)=>ingress.Process(body,"local-message","local-invocation",Now,token);
 public Incident Head(MonitorDefinition m)=>Store.Read(StorageKeys.Aggregate(m.Key))!.Head;
}
