namespace SqlBackup;

public sealed class Protocol(Options options, ISqlEngine? sql, IStore? store)
{
    public void ValidateManifest(Manifest m)
    {
        if (m.SchemaVersion != 1 || !System.Text.RegularExpressions.Regex.IsMatch(m.Id, "^[a-f0-9]{32}$") || m.Database != options.Database ||
            m.Length <= 0 || m.Length > options.MaxBackupBytes || !System.Text.RegularExpressions.Regex.IsMatch(m.Sha256, "^[a-f0-9]{64}$") ||
            !m.NativeChecksumVerified || m.TextKeyArn != options.TextKeyArn || m.BackupKey != options.BackupKey(m.Id) || !m.SqlVersion.StartsWith("16.") ||
            m.CompletedUtc > DateTimeOffset.UtcNow.AddMinutes(5) || m.CompletedUtc < DateTimeOffset.UnixEpoch)
            throw new BackupFailure("MANIFEST_REJECTED");
        if (m.StartedUtc < DateTimeOffset.UnixEpoch || m.StartedUtc > m.CompletedUtc) throw new BackupFailure("MANIFEST_REJECTED");
    }
    private void Match(Stored? actual, string hash, long length, string? version = null)
    {
        if (actual == null || string.IsNullOrWhiteSpace(actual.VersionId) || actual.VersionId == "null" ||
            (version != null && actual.VersionId != version) || actual.KmsKeyArn != options.BackupKeyArn || actual.Sha256 != hash || actual.Length != length)
            throw new BackupFailure("REMOTE_INTEGRITY_UNCONFIRMED");
    }
    private async Task<Stored> CommitObject(string key, string file, string hash, CancellationToken ct)
    {
        var length = new FileInfo(file).Length;
        // UUID keys are new; conditional Put enforces absence. Do not preflight
        // Get: a missing object is 403 for a producer without ListBucket.
        string? version = null;
        try { version = await store!.Put(key, file, hash, ct); }
        catch (Exception) when (!ct.IsCancellationRequested) { /* Ambiguous result: one exact-key readback, never blind resend. */ }
        var observed = await store!.Get(key, version, null, ct);
        Match(observed, hash, length, version);
        return observed!;
    }
    public async Task<Receipt?> Backup(CancellationToken ct)
    {
        options.Validate();
        Local.PrivateDirectory(options.StagingDirectory);
        using var held = new FileStream(Path.Combine(options.StagingDirectory, "operation.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        var id = Guid.NewGuid().ToString("N");
        var directory = Path.Combine(options.StagingDirectory, id); Local.PrivateDirectory(directory);
        var state = Path.Combine(options.StagingDirectory, "last-attempt.json");
        JsonFiles.Write(state, new Attempt(id, "STARTED", DateTimeOffset.UtcNow));
        try
        {
            var info = await sql!.Describe(options.Database, ct);
            if (!info.Version.StartsWith("16.") || info.AllocatedBytes <= 0 || info.AllocatedBytes > options.MaxBackupBytes) throw new BackupFailure("DATABASE_OUTSIDE_LAB_BOUND");
            Local.Space(directory, checked(info.AllocatedBytes * 2 + options.FreeReserveBytes));
            var file = Path.Combine(directory, "database.bak");
            if (File.Exists(file)) throw new BackupFailure("BACKUP_PATH_EXISTS");
            var started = DateTimeOffset.UtcNow;
            await sql.Backup(options.Database, file, ct);
            var completed = DateTimeOffset.UtcNow;
            if ((File.GetAttributes(file) & FileAttributes.ReparsePoint) != 0) throw new BackupFailure("SYMLINK_DENIED");
            if (OperatingSystem.IsLinux()) File.SetUnixFileMode(file, UnixFileMode.UserRead | UnixFileMode.UserWrite);
            var length = new FileInfo(file).Length;
            if (length <= 0 || length > options.MaxBackupBytes) throw new BackupFailure("BACKUP_SIZE_REJECTED");
            await sql.Verify(options.Database, file, ct);
            var manifest = new Manifest(1, id, options.Database, started, completed, info.Version, info.RecoveryModel,
                length, Local.Hash(file), true, options.TextKeyArn, options.BackupKey(id));
            var manifestFile = Path.Combine(directory, "manifest.json"); JsonFiles.Write(manifestFile, manifest);
            if (store == null)
            {
                JsonFiles.Write(state, new Attempt(id, "LOCAL_VERIFIED", DateTimeOffset.UtcNow));
                return null; // Local success is deliberately not a remote-success heartbeat.
            }
            var remote = await CommitObject(manifest.BackupKey, file, manifest.Sha256, ct);
            manifest = manifest with { BackupVersion = remote.VersionId };
            JsonFiles.Write(manifestFile, manifest);
            var committed = await CommitObject(options.ManifestKey(id), manifestFile, Local.Hash(manifestFile), ct);
            var receipt = new Receipt(options.ManifestKey(id), committed.VersionId, manifest);
            JsonFiles.Write(Path.Combine(directory, "receipt.json"), receipt);
            JsonFiles.Write(Path.Combine(options.StagingDirectory, "last-success.json"), receipt);
            JsonFiles.Write(state, new Attempt(id, "REMOTE_VERIFIED", DateTimeOffset.UtcNow));
            return receipt;
        }
        catch (Exception error)
        {
            JsonFiles.Write(state, new Attempt(id, "FAILED", DateTimeOffset.UtcNow, error is BackupFailure failure ? failure.Code : "BACKUP_FAILED"));
            throw;
        }
    }
    public async Task<long> Restore(string manifestKey, string manifestVersion, string target, CancellationToken ct)
    {
        options.Validate(); options.ManifestKeyAllowed(manifestKey); Names.Database(target);
        Local.PrivateDirectory(options.RestoreDirectory);
        if (!target.StartsWith(options.Database + "_restore_", StringComparison.Ordinal) || target == options.Database) throw new BackupFailure("RESTORE_TARGET_DENIED");
        if (string.IsNullOrWhiteSpace(manifestVersion) || manifestVersion == "null") throw new BackupFailure("EXACT_VERSION_REQUIRED");
        var committed = await store!.Get(manifestKey, manifestVersion, null, ct);
        if (committed == null || committed.VersionId != manifestVersion || committed.KmsKeyArn != options.BackupKeyArn || committed.SmallBody == null) throw new BackupFailure("MANIFEST_UNCONFIRMED");
        var manifest = JsonFiles.Parse<Manifest>(committed.SmallBody); ValidateManifest(manifest);
        if (options.ManifestKey(manifest.Id) != manifestKey || string.IsNullOrWhiteSpace(manifest.BackupVersion) || manifest.BackupVersion == "null") throw new BackupFailure("MANIFEST_SCOPE_DENIED");
        using var held = new FileStream(Path.Combine(options.RestoreDirectory, "operation.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        var directory = Path.Combine(options.RestoreDirectory, Guid.NewGuid().ToString("N")); Local.PrivateDirectory(directory);
        Local.Space(directory, checked(manifest.Length * 3 + options.FreeReserveBytes));
        var file = Path.Combine(directory, "download.bak");
        var downloaded = await store.Get(manifest.BackupKey, manifest.BackupVersion, file, ct);
        Match(downloaded, manifest.Sha256, manifest.Length, manifest.BackupVersion);
        if (new FileInfo(file).Length != manifest.Length || Local.Hash(file) != manifest.Sha256) throw new BackupFailure("DOWNLOAD_HASH_MISMATCH");
        await sql!.Verify(manifest.Database, file, ct);
        return await sql.Restore(manifest.Database, file, target, directory, ct);
    }
    public async Task<Health> Check(bool expectedUp, CancellationToken ct)
    {
        if (!expectedUp) return new("MAINTENANCE", "NOT_EXPECTED_UP");
        if (store == null)
        {
            var statePath = Path.Combine(options.StagingDirectory, "last-attempt.json");
            if (File.Exists(statePath) && JsonFiles.Read<Attempt>(statePath).Stage == "FAILED") return new("FAILED", "LAST_ATTEMPT_FAILED");
            return new("UNKNOWN", "REMOTE_STORAGE_NOT_CHECKED");
        }
        DateTimeOffset? latest = null;
        foreach (var key in await store.Manifests(ct))
        {
            options.ManifestKeyAllowed(key);
            var committed = await store.Get(key, null, null, ct);
            if (committed?.SmallBody == null || committed.KmsKeyArn != options.BackupKeyArn || string.IsNullOrEmpty(committed.VersionId) || committed.VersionId == "null") throw new BackupFailure("MANIFEST_UNCONFIRMED");
            var m = JsonFiles.Parse<Manifest>(committed.SmallBody); ValidateManifest(m);
            if (string.IsNullOrWhiteSpace(m.BackupVersion) || m.BackupVersion == "null" || options.ManifestKey(m.Id) != key) throw new BackupFailure("MANIFEST_UNCONFIRMED");
            if (latest == null || m.StartedUtc > latest) latest = m.StartedUtc;
        }
        return latest == null ? new("MISSING", "NO_REMOTE_COMMIT") : DateTimeOffset.UtcNow - latest > TimeSpan.FromHours(options.ProposedMaxAgeHours)
            ? new("STALE", "REMOTE_BACKUP_TOO_OLD", latest) : new("HEALTHY", "RECENT_REMOTE_COMMIT", latest);
    }
}
