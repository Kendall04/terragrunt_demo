using Microsoft.Extensions.Diagnostics.HealthChecks;
using terragrunt_demo.Services;

namespace terragrunt_demo.Health;

public sealed class KmsEncryptionHealthCheck : IHealthCheck
{
    private readonly IEncryptionService _encryptionService;

    public KmsEncryptionHealthCheck(IEncryptionService encryptionService)
    {
        _encryptionService = encryptionService;
    }

    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        try
        {
            await _encryptionService.EncryptAsync("health-check", cancellationToken);
            return HealthCheckResult.Healthy("KMS encryption call succeeded.");
        }
        catch (Exception ex)
        {
            return HealthCheckResult.Unhealthy("KMS encryption call failed.", ex);
        }
    }
}
