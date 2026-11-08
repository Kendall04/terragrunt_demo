using Amazon.KeyManagementService.Model;
using Amazon.KeyManagementService;
using System.Text;

namespace terragrunt_demo.Services
{
    public interface IEncryptionService
    {
        Task<string> EncryptAsync(string plainText, CancellationToken ct = default);
        Task<string> DecryptAsync(string cipherText, CancellationToken ct = default);
    }

    public class KmsEncryptionService : IEncryptionService
    {
        // Current symmetric direct-KMS contract (default SYMMETRIC_DEFAULT):
        // https://docs.aws.amazon.com/kms/latest/APIReference/API_Encrypt.html
        private const int MaxPlaintextBytes = 4096;

        private readonly IAmazonKeyManagementService _kms;
        private readonly string _keyId;

        public KmsEncryptionService(
            IAmazonKeyManagementService kms,
            IConfiguration configuration)
        {
            _kms = kms;
            _keyId = configuration["KMS_KEY_ID"]
                ?? throw new InvalidOperationException("KMS_KEY_ID is not configured");
        }

        public async Task<string> EncryptAsync(string plainText, CancellationToken ct = default)
        {
            if (Encoding.UTF8.GetByteCount(plainText) > MaxPlaintextBytes)
                throw new PlaintextTooLargeException(MaxPlaintextBytes);

            var response = await _kms.EncryptAsync(new EncryptRequest
            {
                KeyId = _keyId,
                Plaintext = new MemoryStream(Encoding.UTF8.GetBytes(plainText))
            }, ct);

            return Convert.ToBase64String(response.CiphertextBlob.ToArray());
        }

        public async Task<string> DecryptAsync(string cipherText, CancellationToken ct = default)
        {
            var response = await _kms.DecryptAsync(new DecryptRequest
            {
                CiphertextBlob = new MemoryStream(Convert.FromBase64String(cipherText))
            }, ct);

            return Encoding.UTF8.GetString(response.Plaintext.ToArray());
        }
    }
}
