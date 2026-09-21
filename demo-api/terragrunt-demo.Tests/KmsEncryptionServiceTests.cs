using System.Text;
using Amazon;
using Amazon.KeyManagementService;
using Amazon.KeyManagementService.Model;
using Amazon.Runtime;
using Microsoft.Extensions.Configuration;
using terragrunt_demo.Services;

namespace terragrunt_demo.Tests;

public class KmsEncryptionServiceTests
{
    public static IEnumerable<object[]> Boundaries()
    {
        yield return new object[] { new string('a', 4095), 4095 };
        yield return new object[] { new string('a', 4096), 4096 };
        yield return new object[] { new string('a', 4097), 4097 };
        yield return new object[] { new string('\u00e9', 2047) + "a", 4095 };
        yield return new object[] { new string('\u00e9', 2048), 4096 };
        yield return new object[] { new string('\u00e9', 2048) + "a", 4097 };
        yield return new object[] { string.Concat(Enumerable.Repeat("\U0001f600", 1024)), 4096 };
        yield return new object[] { string.Concat(Enumerable.Repeat("\U0001f600", 1024)) + "a", 4097 };
    }

    [Theory]
    [MemberData(nameof(Boundaries))]
    public async Task Encrypt_EnforcesEncodedByteBoundary(string input, int byteCount)
    {
        Assert.Equal(byteCount, Encoding.UTF8.GetByteCount(input));
        using var kms = new RecordingKmsClient();
        var service = CreateService(kms);
        using var cancellation = new CancellationTokenSource();

        if (byteCount > 4096)
        {
            var error = await Assert.ThrowsAsync<PlaintextTooLargeException>(
                () => service.EncryptAsync(input, cancellation.Token));
            Assert.Equal(4096, error.MaxPlaintextBytes);
            Assert.DoesNotContain(input, error.Message);
            Assert.Equal(0, kms.EncryptCalls);
        }
        else
        {
            var result = await service.EncryptAsync(input, cancellation.Token);
            Assert.Equal(Convert.ToBase64String(RecordingKmsClient.Ciphertext), result);
            Assert.Equal(1, kms.EncryptCalls);
            Assert.Equal(Encoding.UTF8.GetBytes(input), kms.Plaintext);
            Assert.Equal("test-key", kms.KeyId);
            Assert.Equal(cancellation.Token, kms.Token);
        }
    }

    [Fact]
    public async Task Decrypt_PreservesBase64AndUtf8Conversion()
    {
        using var kms = new RecordingKmsClient();
        using var cancellation = new CancellationTokenSource();
        var result = await CreateService(kms).DecryptAsync(
            Convert.ToBase64String(RecordingKmsClient.Ciphertext), cancellation.Token);
        Assert.Equal("stored \u00e9 \U0001f600", result);
        Assert.Equal(RecordingKmsClient.Ciphertext, kms.DecryptCiphertext);
        Assert.Equal(cancellation.Token, kms.Token);
    }

    private static KmsEncryptionService CreateService(RecordingKmsClient kms) => new(kms,
        new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["KMS_KEY_ID"] = "test-key"
        }).Build());
}

// Explicit credentials/region, with no base SDK operation or network call.
internal sealed class RecordingKmsClient : AmazonKeyManagementServiceClient
{
    public static readonly byte[] Ciphertext = { 0, 127, 128, 255 };
    public int EncryptCalls { get; private set; }
    public byte[]? Plaintext { get; private set; }
    public byte[]? DecryptCiphertext { get; private set; }
    public string? KeyId { get; private set; }
    public CancellationToken Token { get; private set; }

    public RecordingKmsClient() : base(new BasicAWSCredentials("dummy", "dummy"), RegionEndpoint.USEast1) { }

    public override Task<EncryptResponse> EncryptAsync(EncryptRequest request, CancellationToken cancellationToken = default)
    {
        EncryptCalls++;
        Plaintext = request.Plaintext.ToArray();
        KeyId = request.KeyId;
        Token = cancellationToken;
        return Task.FromResult(new EncryptResponse { CiphertextBlob = new MemoryStream(Ciphertext) });
    }

    public override Task<DecryptResponse> DecryptAsync(DecryptRequest request, CancellationToken cancellationToken = default)
    {
        DecryptCiphertext = request.CiphertextBlob.ToArray();
        Token = cancellationToken;
        return Task.FromResult(new DecryptResponse
        {
            Plaintext = new MemoryStream(Encoding.UTF8.GetBytes("stored \u00e9 \U0001f600"))
        });
    }
}
