using Microsoft.Extensions.Diagnostics.HealthChecks;
using terragrunt_demo.Services;

namespace terragrunt_demo.Health;

public sealed class KmsEncryptionHealthCheck : IHealthCheck
{
    private readonly IConfiguration _configuration;
    private readonly IServiceScopeFactory _scopeFactory;

    public KmsEncryptionHealthCheck(
        IConfiguration configuration,
        IServiceScopeFactory scopeFactory)
    {
        _configuration = configuration;
        _scopeFactory = scopeFactory;
    }

    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        var timeoutSeconds = _configuration.GetValue("Kms:HealthCheckTimeoutSeconds", 5);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(timeoutSeconds));

        if (string.IsNullOrWhiteSpace(_configuration["KMS_KEY_ID"]))
        {
            return HealthCheckResult.Unhealthy("KMS_KEY_ID is not configured.");
        }

        try
        {
            using var scope = _scopeFactory.CreateScope();
            var encryptionService = scope.ServiceProvider.GetRequiredService<IEncryptionService>();

            await encryptionService.EncryptAsync("health-check", timeout.Token);
            return HealthCheckResult.Healthy("KMS encryption call succeeded.");
        }
        catch (OperationCanceledException)
        {
            return HealthCheckResult.Unhealthy("KMS encryption call timed out.");
        }
        catch (Exception)
        {
            return HealthCheckResult.Unhealthy("KMS encryption call failed.");
        }
    }
}
