using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging.Abstractions;
using terragrunt_demo.Data;

namespace terragrunt_demo.Tests;

public class TrustTransitionLifetimeTests
{
    private static IConfiguration Config(string env, string? until) =>
        new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string,string?> {
            ["APP_ENV"] = env, ["SQL_TRUST_TRANSITION_UNTIL"] = until }).Build();

    [Theory]
    [InlineData("prod","2026-11-09T00:00:00Z")]
    [InlineData("dev","2026-12-05T00:00:00Z")]
    [InlineData("dev","not-a-date")]
    public void Transition_refuses_prod_unbounded_or_invalid_deadline(string env,string until) =>
        Assert.Throws<InvalidOperationException>(() => TrustTransitionLifetime.Deadline(Config(env,until)));

    [Fact] public void Ordinary_trust_has_no_transition_timer() => Assert.Null(TrustTransitionLifetime.Deadline(Config("prod",null)));

    [Fact] public async Task Expired_transition_stops_the_host_without_resetting_evidence()
    {
        var lifetime = new Lifetime();
        using var service = new TrustTransitionLifetime(Config("dev","2026-01-01T00:00:00Z"),lifetime,
            NullLogger<TrustTransitionLifetime>.Instance,TimeProvider.System);
        await service.StartAsync(CancellationToken.None);
        await lifetime.Stopped.Task.WaitAsync(TimeSpan.FromSeconds(5));
        await service.StopAsync(CancellationToken.None);
    }

    private sealed class Lifetime : IHostApplicationLifetime
    {
        public TaskCompletionSource Stopped { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public CancellationToken ApplicationStarted => CancellationToken.None;
        public CancellationToken ApplicationStopping => CancellationToken.None;
        public CancellationToken ApplicationStopped => CancellationToken.None;
        public void StopApplication() => Stopped.TrySetResult();
    }
}
