using System.Globalization;
using System.Text.RegularExpressions;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Persistence.DynamoDb;
using Sentinel.Persistence.S3;
namespace Ecs.Backup.Managed;

public sealed record BackupSettings(string RunId,string Account,string Region,string Project,string Environment,string Consumer,
 string Subject,CorrelationKey Key,string Owner,TimeSpan EvidenceMaxAge,TimeSpan RecoveryBudget,TimeSpan CheckInterval,TimeSpan ResolutionHold,
 StorageLimits Storage,string SenderLabel,string NotificationMode,DateTimeOffset StartsAt,DateTimeOffset ExpiresAt) {
 public const string CatalogVersion="ecs-backup-observer-v3";
 public string Mode { get; init; } = "synthetic-trial";
 public int ObserverDeadlineSeconds { get; init; }
 public bool ObserverExpectedUp { get; init; }
 public string QueueArn=>$"arn:aws:sqs:{Region}:{Account}:{RunId}-ingestion";
 public string TopicArn=>$"arn:aws:sns:{Region}:{Account}:{RunId}-notices";
 public string FunctionArn(string component)=>$"arn:aws:lambda:{Region}:{Account}:function:{RunId}-{component}";
 public DynamoOptions Dynamo=>new(RunId,Project,Environment,Consumer);
 public ArchiveOptions Archive=>new(RunId+"-"+Account,Project,Environment,Consumer);
 public RecoveryPolicy Policy=>Ecs.Backup.Sentinel.BackupIncidentPolicy.Create(Key,EvidenceMaxAge,RecoveryBudget,CheckInterval,ResolutionHold,Owner);
 public void Validate() {
  ArgumentNullException.ThrowIfNull(Account);ArgumentNullException.ThrowIfNull(Region);
  ArgumentNullException.ThrowIfNull(Key);ArgumentNullException.ThrowIfNull(Storage);
  if(!Regex.IsMatch(RunId??"","^ecs-sentinel-[a-z0-9-]{1,24}$") || !Regex.IsMatch(Account,"^[0-9]{12}$") ||
   !Regex.IsMatch(Region,"^[a-z]{2}-[a-z]+-[0-9]$") || Environment!="sandbox" || Consumer!=RunId ||
   !Regex.IsMatch(Subject??"","^[a-z0-9][a-z0-9._-]{0,63}$") || !Regex.IsMatch(Owner??"","^[a-zA-Z0-9._-]{1,64}$") ||
   !Regex.IsMatch(SenderLabel??"","^[a-zA-Z0-9 ._-]{1,40}$") || NotificationMode is not ("EscalationOnly" or "EscalationAndRecovery") ||
   ObserverDeadlineSeconds is <0 or >86400 || (ObserverDeadlineSeconds>0 && Mode!="observer-check") || Mode is not ("synthetic-trial" or "observer-check") || StartsAt.Offset!=TimeSpan.Zero || ExpiresAt.Offset!=TimeSpan.Zero || ExpiresAt<=StartsAt || ExpiresAt-StartsAt>TimeSpan.FromHours(24))
   throw new ArgumentException("Invalid exclusive backup trial bindings.");
  new global::Sentinel.Ingestion.IngestionOptions(Account,Region,Project,Environment,[Ecs.Backup.Sentinel.ObserverNormalizer.Producer],[Key]).Validate();
  Storage.Validate();Dynamo.Validate();Archive.Validate();_ = Policy;
 }
 public void ValidateInvocation(string functionArn,string component,DateTimeOffset now) {
  Validate();if(functionArn!=FunctionArn(component) || now.Offset!=TimeSpan.Zero || now<StartsAt || now>=ExpiresAt)
   throw new ArgumentException("Unauthorized or expired backup invocation.");
 }
 public static BackupSettings Read(Func<string,string?> get) {
  string Need(string name)=>get(name) is {Length:>0} v?v:throw new ArgumentException("Missing backup runtime binding: "+name);
  TimeSpan Seconds(string name,bool zero=false) {var raw=Need(name);if(!int.TryParse(raw,NumberStyles.None,CultureInfo.InvariantCulture,out var n)||n<(zero?0:1))throw new ArgumentException("Invalid bounded duration.");return TimeSpan.FromSeconds(n);}
  DateTimeOffset Utc(string name) {var raw=Need(name);if(!raw.EndsWith('Z') || !DateTimeOffset.TryParse(raw,CultureInfo.InvariantCulture,DateTimeStyles.None,out var at)||at.Offset!=TimeSpan.Zero)throw new ArgumentException("UTC runtime instant required.");return at;}
  if(get("AWS_PROFILE") is {Length:>0} || get("AWS_SHARED_CREDENTIALS_FILE") is {Length:>0})throw new ArgumentException("Profile fallback forbidden.");
  var region=Need("SENTINEL_REGION");if(Need("AWS_REGION")!=region || Need("SENTINEL_MODE") is not ("synthetic-trial" or "observer-check"))throw new ArgumentException("Runtime region/mode mismatch.");
  var storage=new StorageLimits(DedupRetention:Seconds("SENTINEL_DEDUP_SECONDS"),MaxSignalAge:Seconds("SENTINEL_SIGNAL_AGE_SECONDS"),
   AuditRetention:Seconds("SENTINEL_AUDIT_SECONDS"),EffectRetention:Seconds("SENTINEL_EFFECT_SECONDS"));
  var c=new BackupSettings(Need("SENTINEL_RUN_ID"),Need("SENTINEL_ACCOUNT"),region,Need("SENTINEL_PROJECT"),"sandbox",Need("SENTINEL_CONSUMER"),
   Need("SENTINEL_SUBJECT"),new(Need("SENTINEL_SERVICE"),Need("SENTINEL_SCOPE"),Need("SENTINEL_FAILURE_SIGNATURE")),Need("SENTINEL_OWNER"),
   Seconds("SENTINEL_EVIDENCE_SECONDS"),Seconds("SENTINEL_BUDGET_SECONDS"),Seconds("SENTINEL_CHECK_SECONDS"),Seconds("SENTINEL_HOLD_SECONDS",true),
   storage,Need("SENTINEL_SENDER_LABEL"),Need("SENTINEL_NOTIFICATION_MODE"),Utc("SENTINEL_STARTS_AT"),Utc("SENTINEL_EXPIRES_AT")) {Mode=Need("SENTINEL_MODE")};
  if(get("SENTINEL_WATCHDOG_SECONDS") is {Length:>0} watchdog) {
   if(!int.TryParse(watchdog,NumberStyles.None,CultureInfo.InvariantCulture,out var seconds) || seconds<0 || get("SENTINEL_OBSERVER_EXPECTED_UP") is not ("true" or "false"))throw new ArgumentException("Explicit watchdog policy required.");
   c=c with {ObserverDeadlineSeconds=seconds,ObserverExpectedUp=get("SENTINEL_OBSERVER_EXPECTED_UP")=="true"};
  }
  c.Validate();if(Need("SENTINEL_QUEUE_ARN")!=c.QueueArn || Need("SENTINEL_TABLE")!=c.Dynamo.Table || Need("SENTINEL_TOPIC_ARN")!=c.TopicArn ||
   Need("SENTINEL_BUCKET")!=c.Archive.Bucket || Need("SENTINEL_NAMESPACE")!=c.Dynamo.Namespace || Need("SENTINEL_ARCHIVE_PREFIX")!=c.Archive.Prefix)
   throw new ArgumentException("Resource binding mismatch.");return c;
 }
}
