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

    [Theory]
    [InlineData(0)]
    [InlineData(1)]
    public async Task At_and_after_fixed_cap_stop_the_host(int secondsAfter)
    {
        var lifetime = new Lifetime();
        var clock = new TestClock(Cap.AddSeconds(secondsAfter));
        using var service = new TrustTransitionLifetime(Config("dev","2026-12-04T20:09:56Z"),lifetime,
            NullLogger<TrustTransitionLifetime>.Instance,clock);
        await service.StartAsync(CancellationToken.None);
        await lifetime.Stopped.Task.WaitAsync(TimeSpan.FromSeconds(5));
        await service.StopAsync(CancellationToken.None);
    }

    private static readonly DateTimeOffset Cap = new(2026,12,4,20,9,56,TimeSpan.Zero);

    [Fact] public async Task Running_bridge_stops_exactly_at_deadline_with_test_only_clock()
    {
        var lifetime = new Lifetime(); var clock = new TestClock(Cap.AddSeconds(-1));
        using var service = new TrustTransitionLifetime(Config("dev","2026-12-04T20:09:56Z"),lifetime,
            NullLogger<TrustTransitionLifetime>.Instance,clock);
        await service.StartAsync(CancellationToken.None);
        var timer = await clock.Created.Task.WaitAsync(TimeSpan.FromSeconds(5));
        Assert.False(lifetime.Stopped.Task.IsCompleted);
        Assert.Equal(TimeSpan.FromSeconds(1),timer.DueTime);
        clock.Now=Cap; timer.Fire();
        await lifetime.Stopped.Task.WaitAsync(TimeSpan.FromSeconds(5));
        await service.StopAsync(CancellationToken.None);
    }

    // Only in the test assembly, never an environment override in the product.
    private sealed class TestClock(DateTimeOffset now) : TimeProvider
    {
        public DateTimeOffset Now { get; set; } = now;
        public TaskCompletionSource<TestTimer> Created { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public override DateTimeOffset GetUtcNow() => Now;
        public override ITimer CreateTimer(TimerCallback callback,object? state,TimeSpan dueTime,TimeSpan period)
        {
            var timer=new TestTimer(callback,state,dueTime); Created.SetResult(timer); return timer;
        }
    }

    private sealed class TestTimer(TimerCallback callback,object? state,TimeSpan dueTime) : ITimer
    {
        public TimeSpan DueTime { get; } = dueTime;
        public void Fire() => callback(state);
        public bool Change(TimeSpan dueTime,TimeSpan period) => throw new NotSupportedException();
        public void Dispose() { }
        public ValueTask DisposeAsync() => ValueTask.CompletedTask;
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
