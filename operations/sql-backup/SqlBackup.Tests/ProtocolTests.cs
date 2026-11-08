using System.Security.Cryptography;
using System.Text.Json;
using SqlBackup;
using Xunit;

namespace SqlBackupTests;

public sealed class Lab : IDisposable
{
    public string Root { get; } = Path.Combine(Path.GetTempPath(), "sql-backup-test-" + Guid.NewGuid().ToString("N"));
    public Options Options { get; }
    public FakeSql Sql { get; } = new();
    public MemoryStore Store { get; }
    public Protocol Protocol => new(Options, Sql, Store);
    public Lab()
    {
        Options = new Options { Database = "DemoDb", StagingDirectory = Path.Combine(Root, "backups"), RestoreDirectory = Path.Combine(Root, "restores"), Bucket = "synthetic-backup-test",
            BackupKeyArn = "arn:aws:kms:us-east-1:341936017254:key/00000000-0000-0000-0000-000000000001", TextKeyArn = "arn:aws:kms:us-east-1:341936017254:key/00000000-0000-0000-0000-000000000002" };
        Local.PrivateDirectory(Root); Store = new(Options.BackupKeyArn);
    }
    public void Dispose() { if (Directory.Exists(Root)) Directory.Delete(Root, true); }
}
public sealed class FakeSql : ISqlEngine
{
    public bool FailBackup, FailVerify, TargetExists; public int BackupCalls, RestoreCalls, VerifyCalls;
    public long Allocated = 8388608;
    public Task<SqlInfo> Describe(string database, CancellationToken ct) => Task.FromResult(new SqlInfo("16.0.0000", Allocated, "SIMPLE"));
    public Task Backup(string database, string file, CancellationToken ct)
    {
        BackupCalls++; if (FailBackup) throw new Exception("private-connection-string-not-for-output");
        File.WriteAllBytes(file, Enumerable.Range(0, 256).Select(i => (byte)i).ToArray()); return Task.CompletedTask;
    }
    public Task Verify(string database, string file, CancellationToken ct) { VerifyCalls++; if (FailVerify) throw new BackupFailure("NATIVE_HEADER_REJECTED"); return Task.CompletedTask; }
    public Task<long> Restore(string database, string file, string target, string directory, CancellationToken ct)
    { if (TargetExists) throw new BackupFailure("RESTORE_DATABASE_EXISTS"); RestoreCalls++; return Task.FromResult(1L); }
}
public sealed class MemoryStore(string keyArn) : IStore
{
    public Dictionary<string, (string Version, byte[] Body)> Objects { get; } = new();
    public bool AmbiguousAfterWrite, FailBeforeWrite, FailCommit, CorruptBackup, WrongKey, MissingVersion, DenyReadOfAbsentObject;
    public int BackupPuts; public string? LastRequestedVersion;
    public Task<string?> Put(string key, string file, string sha256, CancellationToken ct)
    {
        if (key.EndsWith("database.bak")) BackupPuts++;
        if (FailBeforeWrite || FailCommit && key.EndsWith("manifest.json")) throw new IOException("synthetic transport error");
        if (Objects.ContainsKey(key)) throw new IOException("precondition failed");
        var version = Guid.NewGuid().ToString("N"); Objects.Add(key, (version, File.ReadAllBytes(file)));
        if (AmbiguousAfterWrite) throw new IOException("synthetic timeout after write");
        return Task.FromResult<string?>(version);
    }
    public Task<Stored?> Get(string key, string? version, string? destination, CancellationToken ct)
    {
        LastRequestedVersion = version;
        if (DenyReadOfAbsentObject && !Objects.ContainsKey(key)) throw new UnauthorizedAccessException("synthetic missing-object 403 without ListBucket");
        if (!Objects.TryGetValue(key, out var entry) || version != null && version != entry.Version) return Task.FromResult<Stored?>(null);
        var bytes = entry.Body.ToArray(); if (CorruptBackup && key.EndsWith("database.bak")) bytes[0] ^= 0xff;
        if (destination != null) { using var file = Local.Create(destination); file.Write(bytes); }
        return Task.FromResult<Stored?>(new Stored(MissingVersion ? "null" : entry.Version, Convert.ToHexStringLower(SHA256.HashData(bytes)), bytes.Length,
            WrongKey ? "wrong-key" : keyArn, bytes.Length <= 65536 ? bytes : null));
    }
    public Task<IReadOnlyList<string>> Manifests(CancellationToken ct) => Task.FromResult<IReadOnlyList<string>>(Objects.Keys.Where(k => k.EndsWith("manifest.json")).ToArray());
    public void EditManifest(string key, Func<Manifest, Manifest> edit)
    {
        var entry = Objects[key]; Objects[key] = (entry.Version, JsonSerializer.SerializeToUtf8Bytes(edit(JsonFiles.Parse<Manifest>(entry.Body)), JsonFiles.Format));
    }
}
public class ProtocolTests
{
    private static readonly CancellationToken Ct = CancellationToken.None;
    [Fact] public async Task BackupReadbackCommitRestoreAndRecentCheck()
    {
        using var lab = new Lab(); var receipt = (await lab.Protocol.Backup(Ct))!;
        Assert.Equal("REMOTE_VERIFIED", JsonFiles.Read<Attempt>(Path.Combine(lab.Options.StagingDirectory, "last-attempt.json")).Stage);
        Assert.Equal(1, await lab.Protocol.Restore(receipt.ManifestKey, receipt.ManifestVersion, "DemoDb_restore_trial", Ct));
        Assert.Equal(receipt.Manifest.BackupVersion, lab.Store.LastRequestedVersion);
        Assert.Equal(1, lab.Sql.RestoreCalls); Assert.Equal("HEALTHY", (await lab.Protocol.Check(true, Ct)).Status);
    }
    [Fact] public async Task LocalBackupIsNotRemoteHeartbeat()
    {
        using var lab = new Lab(); var protocol = new Protocol(lab.Options, lab.Sql, null);
        Assert.Null(await protocol.Backup(Ct)); Assert.False(File.Exists(Path.Combine(lab.Options.StagingDirectory, "last-success.json")));
        Assert.Equal("UNKNOWN", (await protocol.Check(true, Ct)).Status);
    }
    [Theory] [InlineData(true)] [InlineData(false)] public async Task NativeFailuresCannotPublishSuccess(bool backup)
    {
        using var lab = new Lab(); lab.Sql.FailBackup = backup; lab.Sql.FailVerify = !backup;
        await Assert.ThrowsAnyAsync<Exception>(() => lab.Protocol.Backup(Ct)); Assert.Empty(lab.Store.Objects);
        var state = File.ReadAllText(Path.Combine(lab.Options.StagingDirectory, "last-attempt.json"));
        Assert.Contains("FAILED", state); Assert.DoesNotContain("private-connection", state);
    }
    [Fact] public async Task InsufficientSpaceStopsBeforeSqlBackup()
    {
        using var lab = new Lab(); var options = lab.Options with { FreeReserveBytes = long.MaxValue / 4 };
        var error = await Assert.ThrowsAsync<BackupFailure>(() => new Protocol(options, lab.Sql, lab.Store).Backup(Ct));
        Assert.Equal("INSUFFICIENT_SPACE", error.Code); Assert.Equal(0, lab.Sql.BackupCalls);
    }
    [Fact] public async Task LargeDatabaseIsRejectedWithoutTruncation()
    {
        using var lab = new Lab(); lab.Sql.Allocated = lab.Options.MaxBackupBytes + 1;
        await Assert.ThrowsAsync<BackupFailure>(() => lab.Protocol.Backup(Ct)); Assert.Equal(0, lab.Sql.BackupCalls);
    }
    [Theory] [InlineData("hash")] [InlineData("key")] [InlineData("version")]
    public async Task UnconfirmedRemoteObjectNeverCommits(string fault)
    {
        using var lab = new Lab(); lab.Store.CorruptBackup = fault == "hash"; lab.Store.WrongKey = fault == "key"; lab.Store.MissingVersion = fault == "version";
        await Assert.ThrowsAsync<BackupFailure>(() => lab.Protocol.Backup(Ct));
        Assert.DoesNotContain(lab.Store.Objects.Keys, k => k.EndsWith("manifest.json"));
        Assert.Single(Directory.GetFiles(lab.Options.StagingDirectory, "database.bak", SearchOption.AllDirectories));
        Assert.False(File.Exists(Path.Combine(lab.Options.StagingDirectory, "last-success.json")));
    }
    [Fact] public async Task AmbiguousWriteIsResolvedByReadbackWithoutResend()
    {
        using var lab = new Lab(); lab.Store.AmbiguousAfterWrite = true;
        Assert.NotNull(await lab.Protocol.Backup(Ct)); Assert.Equal(1, lab.Store.BackupPuts);
    }
    [Fact] public async Task FreshConditionalWriteNeedsNoMissingObjectPreflightRead()
    {
        using var lab = new Lab(); lab.Store.DenyReadOfAbsentObject = true;
        var receipt = await lab.Protocol.Backup(Ct);
        Assert.NotNull(receipt); Assert.Equal(1, lab.Store.BackupPuts);
        Assert.Equal("HEALTHY", (await lab.Protocol.Check(true, Ct)).Status);
    }
    [Fact] public async Task MissingAfterAmbiguousWriteIsFailure()
    {
        using var lab = new Lab(); lab.Store.FailBeforeWrite = true;
        await Assert.ThrowsAsync<BackupFailure>(() => lab.Protocol.Backup(Ct)); Assert.Equal(1, lab.Store.BackupPuts);
    }
    [Fact] public async Task ManifestFailureLeavesNoSuccessHeartbeat()
    {
        using var lab = new Lab(); lab.Store.FailCommit = true;
        await Assert.ThrowsAsync<BackupFailure>(() => lab.Protocol.Backup(Ct));
        Assert.False(File.Exists(Path.Combine(lab.Options.StagingDirectory, "last-success.json")));
    }
    [Fact] public async Task RestoreCorruptionFailsBeforeNativeRestore()
    {
        using var lab = new Lab(); var receipt = (await lab.Protocol.Backup(Ct))!; lab.Store.CorruptBackup = true;
        await Assert.ThrowsAsync<BackupFailure>(() => lab.Protocol.Restore(receipt.ManifestKey, receipt.ManifestVersion, "DemoDb_restore_trial", Ct)); Assert.Equal(0, lab.Sql.RestoreCalls);
    }
    [Theory] [InlineData("DemoDb")] [InlineData("master")] [InlineData("Other_restore_trial")]
    public async Task RestoreRefusesSourceSystemAndUnrelatedTargets(string target)
    {
        using var lab = new Lab(); var receipt = (await lab.Protocol.Backup(Ct))!;
        await Assert.ThrowsAsync<BackupFailure>(() => lab.Protocol.Restore(receipt.ManifestKey, receipt.ManifestVersion, target, Ct)); Assert.Equal(0, lab.Sql.RestoreCalls);
    }
    [Fact] public async Task RestoreRequiresExactManifestVersion()
    {
        using var lab = new Lab(); var receipt = (await lab.Protocol.Backup(Ct))!;
        await Assert.ThrowsAsync<BackupFailure>(() => lab.Protocol.Restore(receipt.ManifestKey, "other-version", "DemoDb_restore_trial", Ct)); Assert.Equal(0, lab.Sql.RestoreCalls);
    }
    [Fact] public async Task RestoreDoesNotOverwriteAnExistingDatabase()
    {
        using var lab = new Lab(); var receipt = (await lab.Protocol.Backup(Ct))!; lab.Sql.TargetExists = true;
        var error = await Assert.ThrowsAsync<BackupFailure>(() => lab.Protocol.Restore(receipt.ManifestKey, receipt.ManifestVersion, "DemoDb_restore_trial", Ct)); Assert.Equal("RESTORE_DATABASE_EXISTS", error.Code);
    }
    [Theory] [InlineData("key")] [InlineData("database")] [InlineData("checksum")]
    public async Task UntrustedManifestCannotRedirectRestore(string fault)
    {
        using var lab = new Lab(); var receipt = (await lab.Protocol.Backup(Ct))!;
        lab.Store.EditManifest(receipt.ManifestKey, m => fault == "key" ? m with { BackupKey = "other-project/data.bak" } : fault == "database" ? m with { Database = "master" } : m with { NativeChecksumVerified = false });
        await Assert.ThrowsAsync<BackupFailure>(() => lab.Protocol.Restore(receipt.ManifestKey, receipt.ManifestVersion, "DemoDb_restore_trial", Ct)); Assert.Equal(0, lab.Sql.RestoreCalls);
    }
    [Fact] public async Task MissingStaleFutureAndMaintenanceRemainDistinct()
    {
        using var lab = new Lab(); Assert.Equal("MISSING", (await lab.Protocol.Check(true, Ct)).Status);
        Assert.Equal("MAINTENANCE", (await lab.Protocol.Check(false, Ct)).Status);
        var receipt = (await lab.Protocol.Backup(Ct))!;
        lab.Store.EditManifest(receipt.ManifestKey, m => m with { StartedUtc = DateTimeOffset.UtcNow.AddHours(-3), CompletedUtc = DateTimeOffset.UtcNow.AddHours(-3).AddMinutes(1) });
        Assert.Equal("STALE", (await lab.Protocol.Check(true, Ct)).Status);
        lab.Store.EditManifest(receipt.ManifestKey, m => m with { StartedUtc = DateTimeOffset.UtcNow.AddHours(1), CompletedUtc = DateTimeOffset.UtcNow.AddHours(1) });
        await Assert.ThrowsAsync<BackupFailure>(() => lab.Protocol.Check(true, Ct));
    }
    [Fact] public async Task FailedAttemptIsObservableWithoutInventingRemoteSuccess()
    {
        using var lab = new Lab(); lab.Sql.FailBackup = true;
        await Assert.ThrowsAnyAsync<Exception>(() => lab.Protocol.Backup(Ct));
        Assert.Equal("FAILED", (await new Protocol(lab.Options, null, null).Check(true, Ct)).Status);
    }
    [Fact] public void DuplicateJsonAndUnknownFieldsAreRejected()
    {
        Assert.Throws<BackupFailure>(() => JsonFiles.Parse<Options>("{\"Database\":\"A\",\"Database\":\"B\"}"u8.ToArray()));
        Assert.Throws<JsonException>(() => JsonFiles.Parse<Options>("{\"ConnectionString\":\"must-not-be-persisted\"}"u8.ToArray()));
    }
    [Fact] public void SymlinkStagingIsRejected()
    {
        if (!OperatingSystem.IsLinux()) return;
        using var lab = new Lab(); var link = Path.Combine(lab.Root, "redirect"); Directory.CreateSymbolicLink(link, Path.GetTempPath());
        Assert.Throws<BackupFailure>(() => Local.PrivateDirectory(link)); Directory.Delete(link);
    }
    [Fact] public void CloudPreviewIsBoundedAndRetainsEncryptionKeys()
    {
        using var lab = new Lab(); var json = JsonSerializer.Serialize(CloudPreview.Render(lab.Options));
        Assert.Contains("PROPOSED_NOT_INSTALLED", json); Assert.Contains("s3:GetObjectVersion", json); Assert.Contains("s3:prefix", json); Assert.Contains("s3:if-none-match", json);
        Assert.DoesNotContain("s3:DeleteObject", json); Assert.DoesNotContain("iam:PassRole", json); Assert.DoesNotContain("kms:ScheduleKeyDeletion", json); Assert.DoesNotContain("AWS_ACCESS_KEY", json);
    }
}
