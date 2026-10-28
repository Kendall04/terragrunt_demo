using SqlBackup;
using Xunit;

namespace SqlBackupTests;

[CollectionDefinition("Process state", DisableParallelization = true)]
public class ProcessStateCollection { }

[Collection("Process state")]
public class ProcessSafetyTests
{
    [Fact] public async Task CliDoesNotPrintConnectionCredentialsOnFailure()
    {
        using var lab = new Lab(); var config = Path.Combine(lab.Root, "config.json"); JsonFiles.Write(config, lab.Options);
        var originalError = Console.Error; var previousBackup = Environment.GetEnvironmentVariable("SQL_BACKUP_CONNECTION_STRING"); var previousVerify = Environment.GetEnvironmentVariable("SQL_VERIFY_CONNECTION_STRING");
        using var output = new StringWriter();
        try
        {
            Environment.SetEnvironmentVariable("SQL_BACKUP_CONNECTION_STRING", "SENSITIVE_SENTINEL_INVALID_CONNECTION");
            Environment.SetEnvironmentVariable("SQL_VERIFY_CONNECTION_STRING", "SENSITIVE_SENTINEL_INVALID_CONNECTION");
            Console.SetError(output);
            Assert.Equal(1, await Program.Main(["backup", "--config", config]));
            Assert.Contains("OPERATION_FAILED", output.ToString()); Assert.DoesNotContain("SENSITIVE_SENTINEL", output.ToString());
        }
        finally
        {
            Console.SetError(originalError);
            Environment.SetEnvironmentVariable("SQL_BACKUP_CONNECTION_STRING", previousBackup); Environment.SetEnvironmentVariable("SQL_VERIFY_CONNECTION_STRING", previousVerify);
        }
    }
    [Fact] public void OversizedConfigIsRejectedBeforeUnboundedRead()
    {
        using var lab = new Lab(); var path = Path.Combine(lab.Root, "too-large.json"); File.WriteAllBytes(path, new byte[65537]);
        var error = Assert.Throws<BackupFailure>(() => JsonFiles.Read<Options>(path)); Assert.Equal("JSON_TOO_LARGE", error.Code);
    }
    [Fact] public async Task DownCheckDoesNotResolveAnyAwsOrSqlCredentials()
    {
        using var lab = new Lab(); var config = Path.Combine(lab.Root, "config.json"); JsonFiles.Write(config, lab.Options);
        Assert.Equal(0, await Program.Main(["check", "--config", config, "--aws", "--expected-up", "false"]));
    }
}
