using Amazon;
using Amazon.Runtime;
using Amazon.Runtime.CredentialManagement;
using Amazon.S3;
using Amazon.S3.Model;
using Amazon.SecurityToken;
using System.Net;
using System.Security.Cryptography;

namespace SqlBackup;

// Constructed only behind the explicit --aws CLI gate. Tests use IStore fakes.
public sealed class S3Store(Options options, IAmazonS3 client) : IStore
{
    public static async Task<S3Store> Connect(Options options, bool ec2Role, CancellationToken ct)
    {
        options.Validate();
        AWSCredentials credentials;
        if (ec2Role)
        {
            if (!System.Text.RegularExpressions.Regex.IsMatch(options.ExpectedEc2RoleName, "^[A-Za-z0-9+=,.@_-]{1,64}$")) throw new BackupFailure("EXACT_EC2_ROLE_REQUIRED");
            credentials = new InstanceProfileAWSCredentials();
        }
        else if (!new CredentialProfileStoreChain().TryGetAWSCredentials("cnp-cert-dev", out credentials)) throw new BackupFailure("CNP_CERT_DEV_AUTH_REQUIRED");
        using var sts = new AmazonSecurityTokenServiceClient(credentials, new AmazonSecurityTokenServiceConfig { RegionEndpoint = RegionEndpoint.USEast1, MaxErrorRetry = 0, Timeout = TimeSpan.FromSeconds(20) });
        var caller = await sts.GetCallerIdentityAsync(new Amazon.SecurityToken.Model.GetCallerIdentityRequest(), ct);
        if (caller.Account != "341936017254") throw new BackupFailure("AWS_ACCOUNT_MISMATCH");
        if (ec2Role && !caller.Arn.StartsWith("arn:aws:sts::341936017254:assumed-role/" + options.ExpectedEc2RoleName + "/", StringComparison.Ordinal)) throw new BackupFailure("EC2_ROLE_MISMATCH");
        var s3 = new AmazonS3Client(credentials, new AmazonS3Config { RegionEndpoint = RegionEndpoint.USEast1, MaxErrorRetry = 0, Timeout = TimeSpan.FromSeconds(options.TimeoutSeconds) });
        return new(options, s3);
    }
    public PutObjectRequest PutRequest(string key, Stream stream, string sha256) => new()
    {
        BucketName = options.Bucket, ExpectedBucketOwner = "341936017254", Key = key, InputStream = stream,
        ServerSideEncryptionMethod = ServerSideEncryptionMethod.AWSKMS,
        ServerSideEncryptionKeyManagementServiceKeyId = options.BackupKeyArn,
        BucketKeyEnabled = false, IfNoneMatch = "*", ChecksumAlgorithm = ChecksumAlgorithm.SHA256,
        ChecksumSHA256 = Convert.ToBase64String(Convert.FromHexString(sha256)), AutoCloseStream = false
    };
    public async Task<string?> Put(string key, string file, string sha256, CancellationToken ct)
    {
        await using var stream = File.OpenRead(file);
        if (stream.Length > options.MaxBackupBytes) throw new BackupFailure("SINGLE_PUT_BOUND_EXCEEDED");
        var result = await client.PutObjectAsync(PutRequest(key, stream, sha256), ct);
        return result.VersionId;
    }
    public async Task<Stored?> Get(string key, string? version, string? destination, CancellationToken ct)
    {
        GetObjectResponse response;
        try { response = await client.GetObjectAsync(new GetObjectRequest { BucketName = options.Bucket, ExpectedBucketOwner = "341936017254", Key = key, VersionId = version }, ct); }
        catch (AmazonS3Exception error) when (error.StatusCode == HttpStatusCode.NotFound && error.ErrorCode is "NoSuchKey" or "NoSuchVersion" or "NotFound") { return null; }
        using (response)
        {
            if (response.ContentLength <= 0 || response.ContentLength > options.MaxBackupBytes || response.ServerSideEncryptionMethod != ServerSideEncryptionMethod.AWSKMS ||
                response.ServerSideEncryptionKeyManagementServiceKeyId != options.BackupKeyArn || string.IsNullOrWhiteSpace(response.VersionId) || response.VersionId == "null")
                throw new BackupFailure("S3_ENCRYPTION_OR_VERSION_REJECTED");
            await using var output = destination == null ? null : Local.Create(destination);
            using var small = response.ContentLength <= 65536 ? new MemoryStream() : null;
            using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
            var buffer = new byte[65536]; long length = 0; int read;
            while ((read = await response.ResponseStream.ReadAsync(buffer, ct)) != 0)
            {
                length += read;
                if (length > response.ContentLength || length > options.MaxBackupBytes) throw new BackupFailure("S3_BODY_BOUND_EXCEEDED");
                hash.AppendData(buffer, 0, read);
                if (output != null) await output.WriteAsync(buffer.AsMemory(0, read), ct);
                if (small != null) await small.WriteAsync(buffer.AsMemory(0, read), ct);
            }
            if (length != response.ContentLength) throw new BackupFailure("S3_TRUNCATED_BODY");
            return new(response.VersionId, Convert.ToHexStringLower(hash.GetHashAndReset()), length, options.BackupKeyArn, small?.ToArray());
        }
    }
    public async Task<IReadOnlyList<string>> Manifests(CancellationToken ct)
    {
        var keys = new List<string>(); string? token = null; int pages = 0;
        do
        {
            if (++pages > 100) throw new BackupFailure("S3_INVENTORY_BOUND_EXCEEDED");
            var page = await client.ListObjectsV2Async(new ListObjectsV2Request { BucketName = options.Bucket, ExpectedBucketOwner = "341936017254", Prefix = options.Prefix + "/runs/", ContinuationToken = token, MaxKeys = 100 }, ct);
            foreach (var item in page.S3Objects ?? []) if (item.Key.EndsWith("/manifest.json", StringComparison.Ordinal)) keys.Add(item.Key);
            token = page.IsTruncated == true ? page.NextContinuationToken : null;
            if (page.IsTruncated == true && string.IsNullOrEmpty(token)) throw new BackupFailure("S3_PAGINATION_UNCONFIRMED");
        } while (token != null);
        return keys;
    }
}
