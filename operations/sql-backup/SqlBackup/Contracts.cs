using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace SqlBackup;

public sealed class BackupFailure(string code) : Exception(code) { public string Code { get; } = code; }
public sealed record Options
{
    public string Database { get; init; } = "DemoDb";
    public string StagingDirectory { get; init; } = "/var/opt/mssql/backup/v2";
    public string RestoreDirectory { get; init; } = "/var/opt/mssql/backup/v2-restores";
    public string Bucket { get; init; } = "";
    public string Prefix { get; init; } = "terragrunt-demo/dev/sql-backups";
    public string BackupKeyArn { get; init; } = "";
    public string TextKeyArn { get; init; } = "";
    public string ExpectedEc2RoleName { get; init; } = "";
    public long MaxBackupBytes { get; init; } = 536870912;
    public long FreeReserveBytes { get; init; } = 268435456;
    public int TimeoutSeconds { get; init; } = 600;
    public int ProposedIntervalHours { get; init; } = 1;
    public int ProposedRetentionDays { get; init; } = 2;
    public int ProposedMaxAgeHours { get; init; } = 2;
    public void Validate()
    {
        Names.Database(Database);
        if (new[] {"master", "model", "msdb", "tempdb"}.Contains(Database, StringComparer.OrdinalIgnoreCase)) throw new BackupFailure("SYSTEM_DATABASE_DENIED");
        if (!Regex.IsMatch(Prefix, "^[a-z0-9][a-z0-9/_-]{1,120}$") || Prefix.Contains("//")) throw new BackupFailure("INVALID_PREFIX");
        foreach (var key in new[] {BackupKeyArn, TextKeyArn})
            if (!Regex.IsMatch(key, "^arn:aws:kms:us-east-1:341936017254:key/[a-f0-9-]{36}$")) throw new BackupFailure("EXACT_KEY_ARN_REQUIRED");
        if (!Regex.IsMatch(Bucket, "^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$") || Bucket.Contains("..")) throw new BackupFailure("INVALID_BUCKET");
        if (MaxBackupBytes < 1048576 || MaxBackupBytes > 1073741824 || FreeReserveBytes < 1048576 || TimeoutSeconds is < 10 or > 3600) throw new BackupFailure("INVALID_BOUNDS");
        if (ProposedIntervalHours is < 1 or > 24 || ProposedRetentionDays is < 1 or > 30 || ProposedMaxAgeHours < ProposedIntervalHours || ProposedMaxAgeHours > 168) throw new BackupFailure("INVALID_PROPOSED_DEFAULTS");
        if (!Path.IsPathFullyQualified(StagingDirectory) || !Path.IsPathFullyQualified(RestoreDirectory)) throw new BackupFailure("ABSOLUTE_DIRECTORY_REQUIRED");
    }
    public string BackupKey(string id) => $"{Prefix}/runs/{id}/database.bak";
    public string ManifestKey(string id) => $"{Prefix}/runs/{id}/manifest.json";
    public void ManifestKeyAllowed(string key)
    {
        if (!Regex.IsMatch(key, "^" + Regex.Escape(Prefix) + "/runs/[a-f0-9]{32}/manifest\\.json$")) throw new BackupFailure("MANIFEST_SCOPE_DENIED");
    }
}
public static class Names
{
    public static void Database(string value) { if (!Regex.IsMatch(value, "^[A-Za-z][A-Za-z0-9_]{0,63}$")) throw new BackupFailure("INVALID_DATABASE_NAME"); }
    public static string Quote(string value) { Database(value); return "[" + value + "]"; }
}
public sealed record SqlInfo(string Version, long AllocatedBytes, string RecoveryModel);
public interface ISqlEngine
{
    Task<SqlInfo> Describe(string database, CancellationToken ct);
    Task Backup(string database, string file, CancellationToken ct);
    Task Verify(string database, string file, CancellationToken ct);
    Task<long> Restore(string database, string file, string target, string directory, CancellationToken ct);
}
public sealed record Stored(string VersionId, string Sha256, long Length, string KmsKeyArn, byte[]? SmallBody = null);
public interface IStore
{
    Task<string?> Put(string key, string file, string sha256, CancellationToken ct);
    Task<Stored?> Get(string key, string? version, string? destination, CancellationToken ct);
    Task<IReadOnlyList<string>> Manifests(CancellationToken ct);
}
public sealed record Manifest(int SchemaVersion, string Id, string Database, DateTimeOffset StartedUtc, DateTimeOffset CompletedUtc, string SqlVersion,
    string RecoveryModel, long Length, string Sha256, bool NativeChecksumVerified, string TextKeyArn, string BackupKey, string? BackupVersion = null);
public sealed record Receipt(string ManifestKey, string ManifestVersion, Manifest Manifest);
public sealed record Attempt(string Id, string Stage, DateTimeOffset Utc, string? Code = null);
public sealed record Health(string Status, string Code, DateTimeOffset? LastSuccessUtc = null);

public static class JsonFiles
{
    public static readonly JsonSerializerOptions Format = new() { WriteIndented = true, UnmappedMemberHandling = JsonUnmappedMemberHandling.Disallow, MaxDepth = 16 };
    public static T Parse<T>(byte[] bytes)
    {
        if (bytes.Length > 65536) throw new BackupFailure("JSON_TOO_LARGE");
        using var document = JsonDocument.Parse(bytes, new JsonDocumentOptions { MaxDepth = 16 });
        void Unique(JsonElement item)
        {
            if (item.ValueKind == JsonValueKind.Object)
            {
                var names = new HashSet<string>();
                foreach (var p in item.EnumerateObject()) { if (!names.Add(p.Name)) throw new BackupFailure("DUPLICATE_JSON_FIELD"); Unique(p.Value); }
            }
            else if (item.ValueKind == JsonValueKind.Array) foreach (var child in item.EnumerateArray()) Unique(child);
        }
        Unique(document.RootElement);
        return JsonSerializer.Deserialize<T>(bytes, Format) ?? throw new BackupFailure("EMPTY_JSON");
    }
    public static T Read<T>(string path)
    {
        using var file = File.OpenRead(path); var length = file.Length;
        if (length > 65536) throw new BackupFailure("JSON_TOO_LARGE");
        var bytes = new byte[(int)length]; file.ReadExactly(bytes);
        if (file.ReadByte() != -1) throw new BackupFailure("JSON_CHANGED_DURING_READ");
        return Parse<T>(bytes);
    }
    public static void Write(string path, object data)
    {
        var temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        using (var stream = Local.Create(temp)) JsonSerializer.Serialize(stream, data, data.GetType(), Format);
        File.Move(temp, path, true);
    }
}
public static class Local
{
    public static void NoLinks(string path)
    {
        for (var item = new DirectoryInfo(Path.GetFullPath(path)); item != null; item = item.Parent)
            if (item.Exists && (item.Attributes & FileAttributes.ReparsePoint) != 0) throw new BackupFailure("SYMLINK_DENIED");
    }
    public static void PrivateDirectory(string path)
    {
        if (!Path.IsPathFullyQualified(path)) throw new BackupFailure("ABSOLUTE_DIRECTORY_REQUIRED");
        NoLinks(path);
        if (!Directory.Exists(path))
        {
            if (OperatingSystem.IsLinux()) Directory.CreateDirectory(path, UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
            else Directory.CreateDirectory(path);
        }
        if (OperatingSystem.IsLinux() && (File.GetUnixFileMode(path) & (UnixFileMode.GroupRead | UnixFileMode.GroupWrite | UnixFileMode.GroupExecute | UnixFileMode.OtherRead | UnixFileMode.OtherWrite | UnixFileMode.OtherExecute)) != 0)
            throw new BackupFailure("PRIVATE_DIRECTORY_REQUIRED");
    }
    public static FileStream Create(string path)
    {
        var options = new FileStreamOptions { Mode = FileMode.CreateNew, Access = FileAccess.Write, Share = FileShare.None };
        if (OperatingSystem.IsLinux()) options.UnixCreateMode = UnixFileMode.UserRead | UnixFileMode.UserWrite;
        return new(path, options);
    }
    public static void Space(string directory, long required)
    {
        var full = Path.GetFullPath(directory);
        var drive = DriveInfo.GetDrives().Where(d => full == d.Name.TrimEnd(Path.DirectorySeparatorChar) || full.StartsWith(d.Name.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.Ordinal))
            .OrderByDescending(d => d.Name.Length).First();
        if (drive.AvailableFreeSpace < required) throw new BackupFailure("INSUFFICIENT_SPACE");
    }
    public static string Hash(string path)
    {
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0) throw new BackupFailure("SYMLINK_DENIED");
        using var file = File.OpenRead(path); return Convert.ToHexStringLower(SHA256.HashData(file));
    }
}
