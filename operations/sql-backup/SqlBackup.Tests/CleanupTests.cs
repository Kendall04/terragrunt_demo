using SqlBackup;
using Xunit;

namespace SqlBackupTests;

public class CleanupTests
{
    [Fact] public async Task KeepsTwoVerifiedBackupsAndMetadataAndDeletesOnlyOlderBak()
    {
        using var lab = new Lab();
        var receipts = new List<Receipt>();
        for (int i = 0; i < 4; i++) receipts.Add((await lab.Protocol.Backup(CancellationToken.None))!);
        var result = await lab.Protocol.Cleanup(CancellationToken.None);
        Assert.Equal("LOCAL_CLEANUP_VERIFIED", result.Status); Assert.Equal(2, result.DeletedBackups); Assert.Equal(2, result.RetainedBackups);
        Assert.Equal(2, Directory.GetFiles(lab.Options.StagingDirectory, "database.bak", SearchOption.AllDirectories).Length);
        Assert.Equal(4, Directory.GetFiles(lab.Options.StagingDirectory, "receipt.json", SearchOption.AllDirectories).Length);
        Assert.True(File.Exists(Path.Combine(lab.Options.StagingDirectory, receipts[^1].Manifest.Id, "database.bak")));
        Assert.Equal(8, lab.Store.Objects.Count);
        Assert.Equal(0, (await lab.Protocol.Cleanup(CancellationToken.None)).DeletedBackups);
    }

    [Theory] [InlineData("missing")] [InlineData("corrupt")] [InlineData("key")] [InlineData("local")]
    public async Task UnconfirmedRemoteOrChangedLocalBytesAreNeverDeleted(string fault)
    {
        using var lab = new Lab();
        var first = (await lab.Protocol.Backup(CancellationToken.None))!;
        await lab.Protocol.Backup(CancellationToken.None); await lab.Protocol.Backup(CancellationToken.None);
        var file = Path.Combine(lab.Options.StagingDirectory, first.Manifest.Id, "database.bak");
        if (fault == "missing") lab.Store.Objects.Remove(first.Manifest.BackupKey);
        if (fault == "corrupt") lab.Store.CorruptBackup = true;
        if (fault == "key") lab.Store.WrongKey = true;
        if (fault == "local") File.WriteAllText(file, "changed-local-fixture");
        var result = await lab.Protocol.Cleanup(CancellationToken.None);
        Assert.Equal("LOCAL_CLEANUP_PARTIAL", result.Status); Assert.Equal(0, result.DeletedBackups);
        Assert.True(result.UnconfirmedBackups > 0); Assert.True(File.Exists(file));
    }

    [Fact] public async Task LocalOnlyFailureUnknownAndForeignFilesRemain()
    {
        using var lab = new Lab();
        await new Protocol(lab.Options, lab.Sql, null).Backup(CancellationToken.None);
        var foreign = Path.Combine(lab.Options.StagingDirectory, "another-project"); Local.PrivateDirectory(foreign);
        var file = Path.Combine(foreign, "database.bak"); File.WriteAllText(file, "foreign");
        var result = await lab.Protocol.Cleanup(CancellationToken.None);
        Assert.Equal(0, result.DeletedBackups); Assert.True(result.UnconfirmedBackups > 0); Assert.True(result.ForeignEntries > 0);
        Assert.Equal("foreign", File.ReadAllText(file));
    }

    [Fact] public async Task NoStoreCannotAuthorizeDeletion()
    {
        using var lab = new Lab(); await lab.Protocol.Backup(CancellationToken.None);
        await Assert.ThrowsAsync<BackupFailure>(() => new Protocol(lab.Options, null, null).Cleanup(CancellationToken.None));
        Assert.Single(Directory.GetFiles(lab.Options.StagingDirectory, "database.bak", SearchOption.AllDirectories));
    }

    [Fact] public async Task CleanupCannotEnterDuringNativeBackup()
    {
        using var lab = new Lab(); var sql = new WaitingSql(); var protocol = new Protocol(lab.Options, sql, lab.Store);
        var running = protocol.Backup(CancellationToken.None); await sql.Entered.Task;
        try { await Assert.ThrowsAsync<IOException>(() => lab.Protocol.Cleanup(CancellationToken.None)); }
        finally { sql.Release.SetResult(true); }
        await running;
    }

    [Fact] public async Task LinkedRunNeverAuthorizesDeletionOutsideStaging()
    {
        if (!OperatingSystem.IsLinux()) return;
        using var lab = new Lab(); await lab.Protocol.Backup(CancellationToken.None);
        var outside = Path.Combine(lab.Root, "foreign-private"); Local.PrivateDirectory(outside);
        var file = Path.Combine(outside, "database.bak"); File.WriteAllText(file, "outside");
        var link = Path.Combine(lab.Options.StagingDirectory, Guid.NewGuid().ToString("N")); Directory.CreateSymbolicLink(link, outside);
        try { Assert.Equal(0, (await lab.Protocol.Cleanup(CancellationToken.None)).DeletedBackups); Assert.Equal("outside", File.ReadAllText(file)); }
        finally { Directory.Delete(link); }
    }

    [Theory] [InlineData(0)] [InlineData(11)] public void LocalRetentionBoundsAreExplicit(int count)
    {
        using var lab = new Lab(); Assert.Throws<BackupFailure>(() => (lab.Options with { RetainLocalVerifiedBackups = count }).Validate());
    }

    private sealed class WaitingSql : ISqlEngine
    {
        private readonly FakeSql inner = new();
        public TaskCompletionSource<bool> Entered { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public TaskCompletionSource<bool> Release { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public Task<SqlInfo> Describe(string database, CancellationToken ct) => inner.Describe(database, ct);
        public async Task Backup(string database, string file, CancellationToken ct) { Entered.SetResult(true); await Release.Task; await inner.Backup(database, file, ct); }
        public Task Verify(string database, string file, CancellationToken ct) => inner.Verify(database, file, ct);
        public Task<long> Restore(string database, string file, string target, string directory, CancellationToken ct) => inner.Restore(database, file, target, directory, ct);
    }
}
