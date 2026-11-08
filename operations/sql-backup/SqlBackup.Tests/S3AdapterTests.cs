using Amazon;
using Amazon.Runtime;
using Amazon.S3;
using Amazon.S3.Model;
using SqlBackup;
using System.Net;
using System.Security.Cryptography;
using Xunit;

namespace SqlBackupTests;

public sealed class FakeS3 : AmazonS3Client
{
    public Func<GetObjectRequest, GetObjectResponse>? Read;
    public GetObjectRequest? LastRead;
    public ListObjectsV2Request? LastList;
    public FakeS3() : base(new AnonymousAWSCredentials(), RegionEndpoint.USEast1) { }
    public override Task<GetObjectResponse> GetObjectAsync(GetObjectRequest request, CancellationToken cancellationToken = default)
    { LastRead = request; return Task.FromResult(Read!(request)); }
    public override Task<ListObjectsV2Response> ListObjectsV2Async(ListObjectsV2Request request, CancellationToken cancellationToken = default)
    { LastList = request; return Task.FromResult(new ListObjectsV2Response { IsTruncated = true, NextContinuationToken = null }); }
}
public class S3AdapterTests
{
    [Fact] public void PutRequiresConditionalCreationAndExactSseKmsChecksum()
    {
        using var lab = new Lab(); using var sdk = new FakeS3(); var adapter = new S3Store(lab.Options, sdk);
        using var body = new MemoryStream("synthetic"u8.ToArray()); var hash = Convert.ToHexStringLower(SHA256.HashData(body.ToArray()));
        var request = adapter.PutRequest(lab.Options.BackupKey(new string('a', 32)), body, hash);
        Assert.Equal("*", request.IfNoneMatch); Assert.Equal(ServerSideEncryptionMethod.AWSKMS, request.ServerSideEncryptionMethod);
        Assert.Equal("341936017254", request.ExpectedBucketOwner);
        Assert.Equal(lab.Options.BackupKeyArn, request.ServerSideEncryptionKeyManagementServiceKeyId); Assert.False(request.BucketKeyEnabled);
        Assert.Equal(Convert.ToBase64String(Convert.FromHexString(hash)), request.ChecksumSHA256);
    }
    [Fact] public async Task GetHashesActualBytesAndPinsRequestedVersion()
    {
        using var lab = new Lab(); using var sdk = new FakeS3(); var bytes = "synthetic-body"u8.ToArray();
        sdk.Read = _ => new GetObjectResponse { ContentLength = bytes.Length, VersionId = "v1", ResponseStream = new MemoryStream(bytes),
            ServerSideEncryptionMethod = ServerSideEncryptionMethod.AWSKMS, ServerSideEncryptionKeyManagementServiceKeyId = lab.Options.BackupKeyArn };
        var result = await new S3Store(lab.Options, sdk).Get("key", "v1", null, CancellationToken.None);
        Assert.Equal("v1", sdk.LastRead!.VersionId); Assert.Equal(Convert.ToHexStringLower(SHA256.HashData(bytes)), result!.Sha256);
        Assert.Equal("341936017254", sdk.LastRead.ExpectedBucketOwner);
    }
    [Theory] [InlineData("key")] [InlineData("version")] [InlineData("encryption")] [InlineData("truncated")]
    public async Task GetFailsClosedForUnverifiedStorage(string fault)
    {
        using var lab = new Lab(); using var sdk = new FakeS3();
        sdk.Read = _ => new GetObjectResponse { ContentLength = fault == "truncated" ? 10 : 1, VersionId = fault == "version" ? "null" : "v1", ResponseStream = new MemoryStream([1]),
            ServerSideEncryptionMethod = fault == "encryption" ? ServerSideEncryptionMethod.AES256 : ServerSideEncryptionMethod.AWSKMS,
            ServerSideEncryptionKeyManagementServiceKeyId = fault == "key" ? "other-key" : lab.Options.BackupKeyArn };
        await Assert.ThrowsAsync<BackupFailure>(() => new S3Store(lab.Options, sdk).Get("key", "v1", null, CancellationToken.None));
    }
    [Fact] public async Task AccessDeniedIsNotMistakenForMissingBackup()
    {
        using var lab = new Lab(); using var sdk = new FakeS3(); sdk.Read = _ => throw new AmazonS3Exception("synthetic access denied") { StatusCode = HttpStatusCode.Forbidden, ErrorCode = "AccessDenied" };
        await Assert.ThrowsAsync<AmazonS3Exception>(() => new S3Store(lab.Options, sdk).Get("key", null, null, CancellationToken.None));
    }
    [Fact] public async Task IncompletePaginationCannotDeclareHealthy()
    {
        using var lab = new Lab(); using var sdk = new FakeS3();
        await Assert.ThrowsAsync<BackupFailure>(() => new S3Store(lab.Options, sdk).Manifests(CancellationToken.None));
        Assert.Equal("341936017254", sdk.LastList!.ExpectedBucketOwner);
    }
    [Theory] [InlineData("remote.invalid", true)] [InlineData("127.0.0.1", false)]
    public async Task UntrustedNonLocalOrImplicitSqlTlsIsRejectedBeforeNetwork(string host, bool allow)
    {
        var connection = $"Server={host};User ID=synthetic;Password=not-a-real-secret;TrustServerCertificate=True";
        var error = await Assert.ThrowsAsync<BackupFailure>(() => new NativeSql(connection, connection, connection, 10, allow).Describe("DemoDb", CancellationToken.None));
        Assert.Equal("UNTRUSTED_SQL_CERTIFICATE_DENIED", error.Code);
    }
}
