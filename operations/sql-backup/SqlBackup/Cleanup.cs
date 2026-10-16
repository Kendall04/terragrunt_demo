namespace SqlBackup;

public sealed record OwnedRun(int SchemaVersion, string Id, string Database, string Bucket, string Prefix, string BackupKeyArn, string TextKeyArn);
public sealed record CleanupResult(string Status, int DeletedBackups, int RetainedBackups, int UnconfirmedBackups, int ForeignEntries);

public sealed partial class Protocol
{
    public async Task<CleanupResult> Cleanup(CancellationToken ct)
    {
        options.Validate();
        if (store == null) throw new BackupFailure("REMOTE_STORAGE_REQUIRED_FOR_CLEANUP");
        Local.PrivateDirectory(options.StagingDirectory);
        using var held = new FileStream(Path.Combine(options.StagingDirectory, "operation.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        var candidates = new List<(string File, Receipt Receipt)>();
        int foreign = 0, unconfirmed = 0, deleted = 0;
        foreach (var directory in Directory.EnumerateDirectories(options.StagingDirectory))
        {
            ct.ThrowIfCancellationRequested();
            var id = Path.GetFileName(directory);
            if (!System.Text.RegularExpressions.Regex.IsMatch(id, "^[a-f0-9]{32}$")) { foreign++; continue; }
            try
            {
                Local.NoLinks(directory);
                var owner = JsonFiles.Read<OwnedRun>(Path.Combine(directory, "owner.json"));
                if (owner != new OwnedRun(1, id, options.Database, options.Bucket, options.Prefix, options.BackupKeyArn, options.TextKeyArn)) { foreign++; continue; }
                var file = Path.Combine(directory, "database.bak");
                if (!File.Exists(file)) continue; // Already cleaned; metadata is retained.
                var receipt = JsonFiles.Read<Receipt>(Path.Combine(directory, "receipt.json"));
                ValidateManifest(receipt.Manifest);
                if (receipt.Manifest.Id != id || receipt.ManifestKey != options.ManifestKey(id) || string.IsNullOrWhiteSpace(receipt.ManifestVersion) || receipt.ManifestVersion == "null" ||
                    string.IsNullOrWhiteSpace(receipt.Manifest.BackupVersion) || receipt.Manifest.BackupVersion == "null") throw new BackupFailure("CLEANUP_RECEIPT_REJECTED");
                candidates.Add((file, receipt));
            }
            catch (OperationCanceledException) { throw; }
            catch { unconfirmed++; } // No ownership/receipt proof: preserve every byte.
        }
        var ordered = candidates.OrderByDescending(item => item.Receipt.Manifest.StartedUtc).ToList();
        string? last = null;
        try { last = JsonFiles.Read<Receipt>(Path.Combine(options.StagingDirectory, "last-success.json")).Manifest.Id; }
        catch { /* No last-success pointer does not create deletion authority. */ }
        var keep = ordered.Where(item => item.Receipt.Manifest.Id == last).Concat(ordered).Select(item => item.Receipt.Manifest.Id).Distinct().Take(options.RetainLocalVerifiedBackups).ToHashSet();
        int retained = keep.Count;
        foreach (var item in ordered.Where(item => !keep.Contains(item.Receipt.Manifest.Id)))
        {
            ct.ThrowIfCancellationRequested();
            try
            {
                var m = item.Receipt.Manifest;
                var remote = await store.Get(item.Receipt.ManifestKey, item.Receipt.ManifestVersion, null, ct);
                if (remote?.SmallBody == null || remote.VersionId != item.Receipt.ManifestVersion || remote.KmsKeyArn != options.BackupKeyArn || JsonFiles.Parse<Manifest>(remote.SmallBody) != m)
                    throw new BackupFailure("CLEANUP_MANIFEST_UNCONFIRMED");
                Match(await store.Get(m.BackupKey, m.BackupVersion, null, ct), m.Sha256, m.Length, m.BackupVersion);
                Local.NoLinks(Path.GetDirectoryName(item.File)!);
                if (new FileInfo(item.File).Length != m.Length || Local.Hash(item.File) != m.Sha256) throw new BackupFailure("CLEANUP_LOCAL_FILE_CHANGED");
                File.Delete(item.File); // Exactly this owned, remote-confirmed .bak. Never directories, SQL data or S3 objects.
                deleted++;
            }
            catch (OperationCanceledException) { throw; }
            catch { unconfirmed++; }
        }
        var result = new CleanupResult(unconfirmed == 0 ? "LOCAL_CLEANUP_VERIFIED" : "LOCAL_CLEANUP_PARTIAL", deleted, retained, unconfirmed, foreign);
        JsonFiles.Write(Path.Combine(options.StagingDirectory, "last-cleanup.json"), result);
        return result;
    }
}
