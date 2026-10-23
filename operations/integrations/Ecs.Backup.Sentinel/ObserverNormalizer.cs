using System.Collections.Immutable;
using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Ingestion;

namespace Ecs.Backup.Sentinel;

/// <summary>Consumer adapter for the real ISourceNormalizer extension point. No EventBridge impersonation.</summary>
public sealed class ObserverNormalizer(string subject, CorrelationKey key,ITransactionalStore store,RecoveryPolicy policy) : ISourceNormalizer {
    public const string Producer = "SqlBackup.Observer";
    private static readonly string[] Fields = ["SchemaVersion","Source","Subject","ObservedUtc","Status","Code","Severity","LastSuccessUtc","ProducerFailureCoverage","Emit","Reason","Delivery","SentinelIntegrated","RemediationAllowed","Evaluation","CheckInvoked"];
    private static readonly Dictionary<string,string> Pairs = new() {
        ["FAILED"]="LAST_ATTEMPT_FAILED",["MISSING"]="NO_REMOTE_COMMIT",["STALE"]="REMOTE_BACKUP_TOO_OLD",
        ["UNKNOWN"]="REMOTE_STORAGE_NOT_CHECKED",["HEALTHY"]="RECENT_REMOTE_COMMIT",["MAINTENANCE"]="NOT_EXPECTED_UP"
    };
    public sealed record Candidate(bool Emit, string Status, string Code, string Reason, DateTimeOffset Observed,
        DateTimeOffset? LastSuccess, string Evaluation, string FailureCoverage, bool CheckInvoked);
    private static DateTimeOffset Utc(string? value) {
        if (value is null || !Regex.IsMatch(value,@"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,7})?(?:Z|\+00:00)$") ||
            !DateTimeOffset.TryParse(value,CultureInfo.InvariantCulture,DateTimeStyles.None,out var at) || at.Offset!=TimeSpan.Zero)
            throw new JsonException();
        return at;
    }
    public Candidate Read(string body, IngestionOptions options, DateTimeOffset receivedAt) {
        if (Encoding.UTF8.GetByteCount(body)>Math.Min(65536,options.MaxMessageBytes)) throw new JsonException();
        using var doc=JsonDocument.Parse(body,new JsonDocumentOptions { MaxDepth=4 });
        var r=doc.RootElement;
        if (r.ValueKind!=JsonValueKind.Object) throw new JsonException();
        var names=r.EnumerateObject().Select(p=>p.Name).ToArray();
        if (names.Length!=Fields.Length || names.Distinct().Count()!=names.Length || !names.ToHashSet().SetEquals(Fields)) throw new JsonException();
        string Text(string name)=>r.GetProperty(name).GetString()??throw new JsonException();
        if (r.GetProperty("SchemaVersion").GetInt32()!=1 || Text("Source")!=Producer || Text("Subject")!=subject ||
            !Regex.IsMatch(subject,@"^[a-z0-9][a-z0-9._-]{0,63}$") || !options.Producers.Contains(Producer) || !options.Resources.Contains(key) ||
            Text("Delivery")!="NONE" || r.GetProperty("SentinelIntegrated").GetBoolean() || r.GetProperty("RemediationAllowed").GetBoolean()) throw new JsonException();
        var status=Text("Status");var code=Text("Code");var reason=Text("Reason");var emit=r.GetProperty("Emit").GetBoolean();
        if (!Pairs.TryGetValue(status,out var expected) || code!=expected) throw new JsonException();
        var severity=status=="HEALTHY"?"OK":status=="UNKNOWN"?"UNKNOWN":status=="MAINTENANCE"?"MAINTENANCE":"ATTENTION";
        if (Text("Severity")!=severity) throw new JsonException();
        var observed=Utc(Text("ObservedUtc"));
        var last=r.GetProperty("LastSuccessUtc").ValueKind==JsonValueKind.Null?(DateTimeOffset?)null:Utc(Text("LastSuccessUtc"));
        if (receivedAt.Offset!=TimeSpan.Zero || observed>receivedAt || (last is not null && last>observed) ||
            (status is "HEALTHY" or "STALE" && last is null)) throw new JsonException();
        if (emit ? status=="HEALTHY"?reason!="RECOVERED":status=="MAINTENANCE" || reason is not ("INITIAL_ATTENTION" or "CONDITION_CHANGED" or "REMINDER_DUE"):
            reason is not ("UNCHANGED" or "BASELINE_HEALTHY" or "MAINTENANCE")) throw new JsonException();
        if ((reason=="MAINTENANCE")!=(status=="MAINTENANCE") || (reason=="BASELINE_HEALTHY" && status!="HEALTHY")) throw new JsonException();
        var evaluation=Text("Evaluation");var invoked=r.GetProperty("CheckInvoked").GetBoolean();var coverage=Text("ProducerFailureCoverage");
        if (evaluation is not ("CHECK_COMMAND_RESULT" or "LOCAL_RECEIPT_REPLAY" or "EXPECTED_UP_FALSE") ||
            invoked!=(evaluation=="CHECK_COMMAND_RESULT") || (evaluation=="EXPECTED_UP_FALSE")!=(status=="MAINTENANCE") ||
            coverage is not ("NOT_PROVIDED" or "LOCAL_RECEIPT_ONLY")) throw new JsonException();
        return new(emit,status,code,reason,observed,last,evaluation,coverage,invoked);
    }
    private string EventId(Candidate c)=>DomainJson.StableId("ecs-backup-observer-v2",subject,DomainJson.Serialize(c));
    public bool ShouldProcess(Candidate c,DateTimeOffset receivedAt) {
        if(c.Emit)return true;
        if(c.Status!="HEALTHY" || c.Reason!="UNCHANGED")return false;
        var id=EventId(c);var signal=new NormalizedSignal(1,id,Producer,key,SignalKind.Evidence,c.Observed,c.Observed,receivedAt,[]);
        if(store.ReadReceipt(StorageKeys.Receipt(signal),receivedAt) is not null)return true; // Confirmed replay still deduplicates upstream.
        var head=store.Read(StorageKeys.Aggregate(key))?.Head;
        // The upstream reducer requires a second genuine observation to close AUTO_RECOVERED.
        return head is {State:IncidentState.AUTO_RECOVERED,RecoveryConfirmedAt:not null} &&
            c.Observed>head.RecoveryConfirmedAt && c.Observed>=head.RecoveryConfirmedAt+policy.ResolutionHold;
    }
    public AdmissionResult Normalize(string body, IngestionOptions options, DateTimeOffset receivedAt) {
        try {
            var c=Read(body,options,receivedAt);
            if (!ShouldProcess(c,receivedAt)) return new(Admission.UnknownEvent,null,null,"observer-suppressed");
            var id=EventId(c);
            var kind=c.Status=="HEALTHY"?SignalKind.Evidence:c.Status=="UNKNOWN"?SignalKind.TelemetryLost:SignalKind.Failure;
            var signal=new NormalizedSignal(1,id,Producer,key,kind,c.Observed,c.Observed,receivedAt,[],kind==SignalKind.Failure?id:null);
            var metadata=ImmutableDictionary<string,string>.Empty.Add("backupStatus",c.Status).Add("backupCode",c.Code)
                .Add("backupReason",c.Reason).Add("evaluation",c.Evaluation).Add("producerFailureCoverage",c.FailureCoverage)
                .Add("lastSuccessUtc",c.LastSuccess?.ToString("O",CultureInfo.InvariantCulture)??"none");
            var receipt=store.ReadReceipt(StorageKeys.Receipt(signal),receivedAt);
            if(receipt is not null) {
                // Preserve the exact original epoch/evidence across redelivery, recurrence and CAS races.
                var audit=store.ReadAudit(StorageKeys.Audit(StorageKeys.Aggregate(key),receipt.Revision));
                if(audit is null)throw new IngestionException(FailureClass.Transient,"backup-receipt-audit-unavailable");
                if(audit.Signal.Id!=id || audit.Signal.Source!=Producer || audit.Signal.Key!=key ||
                    DomainJson.Fingerprint(audit.Signal)!=receipt.Fingerprint)
                    throw new IngestionException(FailureClass.Security,"backup-receipt-binding");
                signal=audit.Signal with {ReceivedAt=receivedAt};
            } else if(c.Status!="UNKNOWN") {
                var head=store.Read(StorageKeys.Aggregate(key))?.Head;
                var epoch=head is null?1:head.State==IncidentState.RESOLVED && kind==SignalKind.Failure && c.Observed>head.ResolvedAt?head.Epoch+1:head.Epoch;
                var evidence=new RecoveryEvidence(DomainJson.StableId(id,"backup-health"),EvidenceKind.Readiness,key.Scope,Producer,epoch,
                    "backup-health/"+c.Status,c.LastSuccess??c.Observed,c.Observed,c.Observed+policy.EvidenceMaxAge,new() {Ready=c.Status=="HEALTHY"});
                signal=signal with {Evidence=[evidence]};
            }
            // No NAT capacity/EIP/route facts, critical impact, infrastructure mutation or privileged Resolve.
            return new(Admission.Valid,signal,new(id,id,Producer,null),"backup-observer-normalized",metadata);
        } catch (Exception e) when (e is JsonException or InvalidOperationException or KeyNotFoundException or FormatException or ArgumentException or OverflowException) {
            return new(Admission.Malformed,null,null,"backup-observer-contract");
        }
    }
}

/// <summary>Suppress unchanged observations except a fresh recovery confirmation required by the real reducer.</summary>
public sealed class BackupIngress(ObserverNormalizer normalizer, IngestionProcessor processor) {
    public MessageResult? Process(string body, string messageId, DateTimeOffset receivedAt) {
        try { if (!normalizer.ShouldProcess(normalizer.Read(body,processor.Options,receivedAt),receivedAt)) return null; }
        catch (Exception e) when (e is JsonException or InvalidOperationException or KeyNotFoundException or FormatException or ArgumentException or OverflowException) { }
        catch(IOException) {return new(true,FailureClass.Transient,"backup-store-read",null);}
        catch(TimeoutException) {return new(true,FailureClass.Transient,"backup-store-read-timeout",null);}
        return processor.Process(body,messageId,"ecs-backup-local",receivedAt);
    }
}
