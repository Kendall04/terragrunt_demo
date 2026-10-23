using Sentinel.Core;

namespace Ecs.Backup.Sentinel;

/// <summary>Read-only backup-observer assessment using the real Sentinel evaluator extension point.</summary>
public sealed class BackupIncidentPolicy(CorrelationKey key) : IRecoveryEvaluator {
    public static RecoveryPolicy Create(CorrelationKey key,TimeSpan observationMaxAge,TimeSpan recoveryBudget,
        TimeSpan checkInterval,TimeSpan confirmationHold,string owner) {
        if(observationMaxAge<=TimeSpan.Zero || recoveryBudget<=TimeSpan.Zero || checkInterval<=TimeSpan.Zero ||
            confirmationHold<TimeSpan.Zero || string.IsNullOrWhiteSpace(owner)) throw new ArgumentException("Explicit backup policy bounds/owner required.");
        // Legacy upstream schema requires Nat settings even for another evaluator. These are NOT AWS bindings or NAT facts.
        // Only a backup-scoped read-probe intent may be produced; no dispatcher/provider is installed by this consumer.
        var version="ecs-backup-v1-"+DomainJson.StableId(DomainJson.Serialize(key),observationMaxAge.Ticks.ToString(System.Globalization.CultureInfo.InvariantCulture),recoveryBudget.Ticks.ToString(System.Globalization.CultureInfo.InvariantCulture),checkInterval.Ticks.ToString(System.Globalization.CultureInfo.InvariantCulture),confirmationHold.Ticks.ToString(System.Globalization.CultureInfo.InvariantCulture),owner);
        return new(new(version),recoveryBudget,observationMaxAge,checkInterval,TimeSpan.Zero,
            TimeSpan.Zero,observationMaxAge,1,TimeSpan.Zero,
            new(1,key.Scope,key.Scope,"unused-by-backup-evaluator",[key.Scope],[ObserverNormalizer.Producer]),owner,null,
            ResolutionHold:confirmationHold);
    }
    public RecoveryAssessment Assess(Incident incident,RecoveryPolicy policy,EvaluationContext context) {
        var observations=incident.Evidence.Where(e=>e.Source==ObserverNormalizer.Producer && e.Scope==key.Scope &&
            incident.Key==key && e.Epoch==incident.Epoch && e.ObservedAt<=context.Now &&
            ((e.Kind==EvidenceKind.Readiness &&
                ((e.Generation=="backup-health/HEALTHY" && e.Facts.Ready==true) ||
                 (e.Generation is "backup-health/FAILED" or "backup-health/MISSING" or "backup-health/STALE" && e.Facts.Ready==false))) ||
             (e.Kind==EvidenceKind.Telemetry && e.Facts.TelemetryAvailable==false))).ToArray();
        RecoveryAssessment Result(RecoveryStatus status,ReasonCode code,string detail,string[] ids)=>new(status,
            [new(code,"backup.observer",detail,[..ids])],[..ids],incident.Impacts.Any(i=>i.Level is not null));
        RecoveryAssessment Unknown(string detail,string[] ids)=>Result(context.Now>=incident.DeadlineAt?RecoveryStatus.Overdue:RecoveryStatus.InsufficientEvidence,
            context.Now>=incident.DeadlineAt?ReasonCode.RecoveryOverdue:ReasonCode.MissingEvidence,detail,ids);
        if(observations.Length==0)return Unknown("No current-episode backup observation.",[]);
        var newest=observations.Max(e=>e.ObservedAt);var latest=observations.Where(e=>e.ObservedAt==newest).ToArray();
        var ids=latest.Select(e=>e.Id).Order(StringComparer.Ordinal).ToArray();
        if(latest.Any(e=>e.ValidUntil<=context.Now || e.ObservedAt+policy.EvidenceMaxAge<=context.Now))
            return Unknown("Latest backup observation expired; no older positive fallback.",ids);
        if(latest.Any(e=>e.Kind==EvidenceKind.Telemetry))return Unknown("Backup observer is UNKNOWN, not missing or recovered.",ids);
        if(latest.Any(e=>e.Facts.Ready==false))return Result(RecoveryStatus.Failed,ReasonCode.FunctionalFailure,"Backup FAILED/MISSING/STALE needs human attention; no infrastructure repair.",ids);
        if(newest<=incident.LastFailureAt)return Unknown("Healthy observation must be strictly newer than the last failure.",ids);
        return Result(RecoveryStatus.Successful,ReasonCode.RecoverySuccessful,"A fresh later backup-health observation is healthy; this is not database/NAT recovery.",ids);
    }
}
