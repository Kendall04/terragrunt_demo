using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using terragrunt_demo.Data;

namespace terragrunt_demo.Health;

public sealed class DatabaseConnectivityHealthCheck : IHealthCheck
{
    private readonly IConfiguration _configuration;
    private readonly IServiceScopeFactory _scopeFactory;

    public DatabaseConnectivityHealthCheck(
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
        var timeoutSeconds = _configuration.GetValue("Database:HealthCheckTimeoutSeconds", 5);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(timeoutSeconds));

        try
        {
            using var scope = _scopeFactory.CreateScope();
            var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();

            if (!await db.Database.CanConnectAsync(timeout.Token))
            {
                return HealthCheckResult.Unhealthy("Database connection failed.");
            }

            var pendingMigrations = await db.Database.GetPendingMigrationsAsync(timeout.Token);
            if (pendingMigrations.Any())
            {
                return HealthCheckResult.Unhealthy("Database has pending migrations.");
            }

            return HealthCheckResult.Healthy("Database connection succeeded.");
        }
        catch (OperationCanceledException)
        {
            return HealthCheckResult.Unhealthy("Database connection timed out.");
        }
        catch (InvalidOperationException ex)
            when (ex.Message.Contains("DB_CONN_STRING", StringComparison.Ordinal))
        {
            return HealthCheckResult.Unhealthy(ex.Message);
        }
        catch (Exception)
        {
            return HealthCheckResult.Unhealthy("Database connection failed.");
        }
    }
}
