using System.Globalization;

namespace terragrunt_demo.Data;

// A running bridge must not keep a temporary trust exception indefinitely.
public sealed class TrustTransitionLifetime(IConfiguration configuration,
    IHostApplicationLifetime lifetime, ILogger<TrustTransitionLifetime> logger,
    TimeProvider clock) : BackgroundService
{
    public static DateTimeOffset? Deadline(IConfiguration configuration)
    {
        var value = configuration["SQL_TRUST_TRANSITION_UNTIL"];
        if (string.IsNullOrEmpty(value)) return null;
        if (configuration["APP_ENV"] != "dev" ||
            !DateTimeOffset.TryParseExact(value, "yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture,
                DateTimeStyles.AssumeUniversal, out var deadline) ||
            deadline > new DateTimeOffset(2026, 12, 4, 20, 9, 56, TimeSpan.Zero))
            throw new InvalidOperationException("SQL_TRUST_TRANSITION_REFUSED");
        return deadline;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var deadline = Deadline(configuration);
        if (deadline is null) return;
        var remaining = deadline.Value - clock.GetUtcNow();
        if (remaining > TimeSpan.Zero) await Task.Delay(remaining, clock, stoppingToken);
        logger.LogCritical("SQL_TRUST_TRANSITION_EXPIRED: stopping API; re-admission required.");
        lifetime.StopApplication();
    }
}
