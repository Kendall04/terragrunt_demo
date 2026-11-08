using System.Security.Cryptography;
using System.Text.Json;

namespace SqlBackup;

// Captured metadata only. Never a live S3 adapter or proof of remote absence.
internal sealed class ReceiptReplayStore(Options options, Receipt[] receipts) : IStore
{
    public static IStore Load(Options options, string path)
    {
        var receipts = JsonFiles.Read<Receipt[]>(path);
        if (receipts.Select(r => r.ManifestKey).Distinct().Count() != receipts.Length) throw new BackupFailure("REPLAY_DUPLICATE_MANIFEST");
        return new ReceiptReplayStore(options, receipts);
    }
    public Task<string?> Put(string key, string file, string hash, CancellationToken ct) => throw new BackupFailure("REPLAY_READ_ONLY");
    public Task<IReadOnlyList<string>> Manifests(CancellationToken ct) => Task.FromResult<IReadOnlyList<string>>(receipts.Select(r => r.ManifestKey).ToArray());
    public Task<Stored?> Get(string key, string? version, string? destination, CancellationToken ct)
    {
        if (destination != null) throw new BackupFailure("REPLAY_READ_ONLY");
        var receipt = receipts.SingleOrDefault(r => r.ManifestKey == key);
        if (receipt == null || version != null && version != receipt.ManifestVersion) return Task.FromResult<Stored?>(null);
        var body = JsonSerializer.SerializeToUtf8Bytes(receipt.Manifest, JsonFiles.Format);
        return Task.FromResult<Stored?>(new Stored(receipt.ManifestVersion, Convert.ToHexStringLower(SHA256.HashData(body)), body.Length, options.BackupKeyArn, body));
    }
}
