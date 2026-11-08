using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Persistence.DynamoDb;
internal static class MonitorSupersessionChecks {
 public static void Run(StoredSnapshot snapshot,IEnumerable<OutboxEntry> effects,Action<string,bool> check) {
  var head=snapshot.Head with{ContinuousMonitoring=true};snapshot=snapshot with{Head=head};
  var checkEntry=effects.First(e=>e.Intent?.Kind==EffectKind.ScheduleRecoveryCheck) with{DueAt=head.LastEvaluatedAt.AddMinutes(-1),CancelIfObsolete=true,Critical=false};
  check("only a later durable evaluation supersedes the timer",DynamoStore.SupersededMonitorCheck(checkEntry,snapshot));
  foreach(var e in new[]{checkEntry with{DueAt=head.LastEvaluatedAt},checkEntry with{DueAt=head.LastEvaluatedAt.AddMinutes(1)},checkEntry with{Critical=true},checkEntry with{CancelIfObsolete=false},checkEntry with{Kind=WorkKind.ArchiveDecision},checkEntry with{AggregateKey="foreign"},checkEntry with{Intent=checkEntry.Intent! with{Kind=EffectKind.OpenIncident}},checkEntry with{Intent=checkEntry.Intent! with{Epoch=head.Epoch+1}}})
   check("uncovered work and effects are never superseded",!DynamoStore.SupersededMonitorCheck(e,snapshot));
  check("missing head is not evidence of supersession",!DynamoStore.SupersededMonitorCheck(checkEntry,null));
  check("non-monitor recovery unchanged",!DynamoStore.SupersededMonitorCheck(checkEntry,snapshot with{Head=head with{ContinuousMonitoring=false}}));
 }
}
