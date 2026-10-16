using System.Text.Json;

namespace SqlBackup;

public static class Program
{
    public static async Task<int> Main(string[] args)
    {
        try
        {
            if (args.Length < 3 || !new[] {"backup", "restore", "check", "cloud-preview"}.Contains(args[0])) throw new BackupFailure("USAGE_REQUIRED");
            var values = new Dictionary<string, string>(); bool aws = false, ec2Role = false, localSql = false;
            for (int i = 1; i < args.Length; i++)
            {
                if (args[i] == "--aws") { if (aws) throw new BackupFailure("DUPLICATE_ARGUMENT"); aws = true; continue; }
                if (args[i] == "--ec2-role") { if (ec2Role) throw new BackupFailure("DUPLICATE_ARGUMENT"); ec2Role = true; continue; }
                if (args[i] == "--local-sql-self-signed") { if (localSql) throw new BackupFailure("DUPLICATE_ARGUMENT"); localSql = true; continue; }
                if (!new[] {"--config", "--manifest-key", "--manifest-version", "--target", "--expected-up"}.Contains(args[i]) || i + 1 >= args.Length || !values.TryAdd(args[i], args[++i])) throw new BackupFailure("INVALID_ARGUMENT");
            }
            if (!values.TryGetValue("--config", out var config)) throw new BackupFailure("CONFIG_REQUIRED");
            var options = JsonFiles.Read<Options>(config); options.Validate();
            if (ec2Role && !aws) throw new BackupFailure("EXPLICIT_AWS_GATE_REQUIRED");
            if (args[0] == "cloud-preview") { Console.WriteLine(JsonSerializer.Serialize(CloudPreview.Render(options), JsonFiles.Format)); return 0; }
            using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(options.TimeoutSeconds));
            var ct = deadline.Token;
            if (args[0] == "check" && values.GetValueOrDefault("--expected-up") == "false")
            { Console.WriteLine(JsonSerializer.Serialize(new Health("MAINTENANCE", "NOT_EXPECTED_UP"))); return 0; }
            IStore? store = aws ? await S3Store.Connect(options, ec2Role, ct) : null;
            NativeSql? engine = null;
            if (args[0] is "backup" or "restore")
            {
                string Credential(string name) => Environment.GetEnvironmentVariable(name) ?? throw new BackupFailure("SQL_CREDENTIAL_REQUIRED");
                engine = args[0] == "backup" ? new(Credential("SQL_BACKUP_CONNECTION_STRING"), Credential("SQL_VERIFY_CONNECTION_STRING"), "", options.TimeoutSeconds, localSql)
                    : new("", Credential("SQL_RESTORE_CONNECTION_STRING"), Credential("SQL_RESTORE_CONNECTION_STRING"), options.TimeoutSeconds, localSql);
            }
            var protocol = new Protocol(options, engine, store);
            if (args[0] == "backup")
            {
                var receipt = await protocol.Backup(ct);
                Console.WriteLine(JsonSerializer.Serialize(new { Status = receipt == null ? "LOCAL_VERIFIED" : "REMOTE_VERIFIED", Receipt = receipt }, JsonFiles.Format));
            }
            else if (args[0] == "restore")
            {
                if (!aws) throw new BackupFailure("EXACT_REMOTE_RESTORE_REQUIRED");
                var rows = await protocol.Restore(values["--manifest-key"], values["--manifest-version"], values["--target"], ct);
                Console.WriteLine(JsonSerializer.Serialize(new { Status = "RESTORED_CHECKDB_READABLE", Rows = rows }));
            }
            else
            {
                if (!values.TryGetValue("--expected-up", out var expected) || !bool.TryParse(expected, out var up)) throw new BackupFailure("EXPECTED_UP_REQUIRED");
                var health = await protocol.Check(up, ct); Console.WriteLine(JsonSerializer.Serialize(health));
                return health.Status is "HEALTHY" or "MAINTENANCE" ? 0 : 1;
            }
            return 0;
        }
        catch (Exception error)
        {
            // Do not print SQL/SDK exceptions, connection strings, rows, credentials or stack traces.
            Console.Error.WriteLine(JsonSerializer.Serialize(new { Status = "FAILED", Code = error is BackupFailure failure ? failure.Code : error is OperationCanceledException ? "DEADLINE_EXCEEDED" : "OPERATION_FAILED" }));
            return 1;
        }
    }
}
