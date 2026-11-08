using Sentinel.Core;
using Sentinel.Portable;
using Sentinel.Portable.Aws;
using Ecs.Backup.Portable;
var c=StrictJson.Installation(File.ReadAllText(Path.Combine(args.Single(),"sentinel.json")));var m=c.Monitors.Single(x=>x.Id=="sql-backup");
var cases=new List<string>();void Check(string n,bool v){if(!v)throw new Exception(n);cases.Add(n);}
var at=DateTimeOffset.Parse("2026-10-26T03:00:00Z");
var n=new IncidentNotice(new string('d',64),c.Deployment,m.Id,new string('i',64),1,"EscalateIncident","Kendall",false,"ESCALATED","InsufficientEvidence",["No current evidence from sql-observer."],new string('a',64),m.Resource,m.Generation,m.RequiredAssurance,2,c.Consumer,3,at,NoticeCondition.HealthUnverifiable,"Health cannot be verified: required evidence is missing.",false);
var raw=DomainJson.Serialize(n);var first=ReadableNotice.Render(n,c,true);
Check("exact upstream schema2 contract renders prominent synthetic mark",first.Message.StartsWith("PRUEBA SINTÉTICA") && first.Subject.StartsWith("PRUEBA SINTÉTICA"));
Check("unknown is not relabelled as confirmed service failure",first.Message.Contains("SALUD NO VERIFICABLE") && !first.Message.Contains("IMPACTO CONFIRMADO"));
Check("revision and evaluation time preserved",first.Message.Contains("Revisión: 3") && first.Message.Contains(at.ToString("O")));
foreach(var value in new[]{n.DeliveryId,n.AuditId,n.IncidentId,n.Generation!,n.Consumer,n.Resource!})Check("operational identity preserved "+value[..Math.Min(8,value.Length)],first.Message.Contains(value));
Check("SNS acceptance and inbox receipt remain distinct",first.Message.Contains("SNS_PUBLISH_ONLY_NOT_INBOX_RECEIPT") && first.Message.Contains("no acredita recepción en inbox"));
Check("no automatic SQL restore or health claim",first.Message.Contains("No implica una restauración SQL"));
Check("same immutable decision renders identical retry",ReadableNotice.Render(n,c,true)==first);
Check("formatter never modifies original structured evidence",DomainJson.Serialize(n)==raw);
Check("human body is not a raw JSON blob",!first.Message.StartsWith("{") && first.Message.Contains("Datos técnicos"));
foreach(var bad in new[]{n with{SchemaVersion=1},n with{Consumer="foreign"},n with{Generation="foreign"},n with{Resource="foreign"},n with{ConfirmedServiceImpact=true},n with{Summary="unsafe\nheader"}}){try{ReadableNotice.Render(bad,c,true);throw new Exception("NOT_REFUSED");}catch(ArgumentException){cases.Add("unsafe or mismatched notice refused");}}
var recovered=n with{Event="ResolveIncident",Condition=NoticeCondition.ExpectationSatisfied,Summary="Evidence satisfies configured expectation.",State="RESOLVED",Assessment="Successful",Revision=4};
Check("resolution has a clear scoped heading",ReadableNotice.Render(recovered,c,true).Message.Contains("RECUPERACIÓN VERIFICADA PARA ESTA EXPECTATIVA"));
Console.WriteLine(DomainJson.Serialize(new{Status="PASS",Tests=cases.Count,Cases=cases,Contract="EXACT_UPSTREAM_SOURCE_ENUM_RECORD",OriginalSnsImplementationExecuted=false,SdkProbeBlocked="CACHE_HASH_MISMATCH_NO_BYPASS",AwsCalls=0,EmailSent=false}));
