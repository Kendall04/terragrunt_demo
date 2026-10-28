using SqlBackup;
using Xunit;

namespace SqlBackupTests;

public sealed class BackupHealthSignalTests
{
    private static readonly CancellationToken Ct = CancellationToken.None;

    [Fact]
    public async Task RecentRemoteSuccessCannotHideLatestFailedAttempt()
    {
        using var lab = new Lab();
        await lab.Protocol.Backup(Ct);
        Assert.Equal("HEALTHY", (await lab.Protocol.Check(true, Ct)).Status);
        lab.Sql.FailBackup = true;
        await Assert.ThrowsAnyAsync<Exception>(() => lab.Protocol.Backup(Ct));

        var health = await lab.Protocol.Check(true, Ct);
        Assert.Equal("FAILED", health.Status);
        Assert.Equal("LAST_ATTEMPT_FAILED", health.Code);
        Assert.DoesNotContain("private-connection", System.Text.Json.JsonSerializer.Serialize(health));
        Assert.Contains(lab.Store.Objects.Keys, key => key.EndsWith("manifest.json"));
    }

    [Fact]
    public async Task MaintenanceSuppressesSignalWithoutErasingFailureEvidence()
    {
        using var lab = new Lab();
        await lab.Protocol.Backup(Ct);
        lab.Sql.FailBackup = true;
        await Assert.ThrowsAnyAsync<Exception>(() => lab.Protocol.Backup(Ct));
        var path = Path.Combine(lab.Options.StagingDirectory, "last-attempt.json");
        var evidence = File.ReadAllBytes(path);

        var down = await lab.Protocol.Check(false, Ct);
        Assert.Equal("MAINTENANCE", down.Status);
        Assert.Equal("NOT_EXPECTED_UP", down.Code);
        Assert.Equal(evidence, File.ReadAllBytes(path));
        Assert.Equal("FAILED", (await lab.Protocol.Check(true, Ct)).Status);
    }

    [Fact]
    public async Task LaterVerifiedBackupClearsFailureThroughNormalStateTransition()
    {
        using var lab = new Lab();
        await lab.Protocol.Backup(Ct);
        lab.Sql.FailBackup = true;
        await Assert.ThrowsAnyAsync<Exception>(() => lab.Protocol.Backup(Ct));
        Assert.Equal("FAILED", (await lab.Protocol.Check(true, Ct)).Status);

        lab.Sql.FailBackup = false;
        await lab.Protocol.Backup(Ct);
        var health = await lab.Protocol.Check(true, Ct);
        Assert.Equal("HEALTHY", health.Status);
        Assert.Equal("RECENT_REMOTE_COMMIT", health.Code);
        Assert.Equal("REMOTE_VERIFIED", JsonFiles.Read<Attempt>(Path.Combine(lab.Options.StagingDirectory, "last-attempt.json")).Stage);
    }

    [Fact]
    public async Task MissingStaleUnknownAndMaintenanceHaveDistinctConsumerCodes()
    {
        using var lab = new Lab();
        var missing = await lab.Protocol.Check(true, Ct);
        Assert.Equal(("MISSING", "NO_REMOTE_COMMIT"), (missing.Status, missing.Code));
        var localOnly = await new Protocol(lab.Options, null, null).Check(true, Ct);
        Assert.Equal(("UNKNOWN", "REMOTE_STORAGE_NOT_CHECKED"), (localOnly.Status, localOnly.Code));
        var down = await lab.Protocol.Check(false, Ct);
        Assert.Equal(("MAINTENANCE", "NOT_EXPECTED_UP"), (down.Status, down.Code));

        var receipt = (await lab.Protocol.Backup(Ct))!;
        lab.Store.EditManifest(receipt.ManifestKey, manifest => manifest with
        {
            StartedUtc = DateTimeOffset.UtcNow.AddHours(-3),
            CompletedUtc = DateTimeOffset.UtcNow.AddHours(-3).AddMinutes(1)
        });
        var stale = await lab.Protocol.Check(true, Ct);
        Assert.Equal(("STALE", "REMOTE_BACKUP_TOO_OLD"), (stale.Status, stale.Code));
    }

    [Fact]
    public async Task IndependentObserverCannotClaimItReadProducerLocalFailure()
    {
        using var lab = new Lab();
        await lab.Protocol.Backup(Ct);
        lab.Sql.FailBackup = true;
        await Assert.ThrowsAnyAsync<Exception>(() => lab.Protocol.Backup(Ct));
        var observerOptions = lab.Options with { StagingDirectory = Path.Combine(lab.Root, "separate-observer") };

        var remoteOnly = await new Protocol(observerOptions, null, lab.Store).Check(true, Ct);
        Assert.Equal(("HEALTHY", "RECENT_REMOTE_COMMIT"), (remoteOnly.Status, remoteOnly.Code));
        Assert.False(Directory.Exists(observerOptions.StagingDirectory));
        Assert.Equal("FAILED", JsonFiles.Read<Attempt>(Path.Combine(lab.Options.StagingDirectory, "last-attempt.json")).Stage);
    }
}
