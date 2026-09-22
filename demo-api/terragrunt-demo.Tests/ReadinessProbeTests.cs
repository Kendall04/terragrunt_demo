using System.Net;
using System.Text;

namespace terragrunt_demo.Tests;

public class ReadinessProbeTests
{
    private const string Healthy = """
        {"status":"Healthy","checks":[{"name":"database","status":"Healthy"},{"name":"kms","status":"Healthy"}]}
        """;
    private const string Unhealthy = """
        {"status":"Unhealthy","checks":[{"name":"database","status":"Unhealthy"},{"name":"kms","status":"Healthy"}]}
        """;

    [Fact]
    public async Task TransientStartup_CanReachConsecutiveSuccessesWithinOneDeadline()
    {
        var handler = new SequenceHandler(
            new(HttpStatusCode.ServiceUnavailable, Unhealthy),
            new(HttpStatusCode.OK, Healthy),
            new(HttpStatusCode.OK, Healthy),
            new(HttpStatusCode.OK, Healthy));
        var clock = new ManualTimeProvider();

        var exitCode = await ReadinessProbe.RunAsync(
            Options(consecutiveSuccesses: 3),
            handler,
            clock.Delay,
            clock);

        Assert.Equal(0, exitCode);
        Assert.Equal(4, handler.RequestCount);
        Assert.All(handler.Requests, request => Assert.Equal("http://127.0.0.1:8080/ready", request));
    }

    [Fact]
    public async Task FailureAfterIsolatedSuccess_ResetsTheStreak()
    {
        var handler = new SequenceHandler(
            new(HttpStatusCode.OK, Healthy),
            new(HttpStatusCode.ServiceUnavailable, Unhealthy),
            new(HttpStatusCode.OK, Healthy),
            new(HttpStatusCode.OK, Healthy));
        var clock = new ManualTimeProvider();

        var exitCode = await ReadinessProbe.RunAsync(
            Options(totalSeconds: 4, consecutiveSuccesses: 3),
            handler,
            clock.Delay,
            clock);

        Assert.Equal(1, exitCode);
        Assert.Equal(4, handler.RequestCount);
    }

    [Fact]
    public async Task PermanentlyUnreadyCandidate_IsBoundedAndFails()
    {
        var handler = new SequenceHandler(new ResponseSpec(HttpStatusCode.OK, Unhealthy));
        var clock = new ManualTimeProvider();

        var exitCode = await ReadinessProbe.RunAsync(
            Options(totalSeconds: 3),
            handler,
            clock.Delay,
            clock);

        Assert.Equal(1, exitCode);
        Assert.Equal(3, handler.RequestCount);
        Assert.Equal(TimeSpan.FromSeconds(3), clock.Elapsed);
    }

    [Theory]
    [InlineData(HttpStatusCode.Redirect, Healthy)]
    [InlineData(HttpStatusCode.OK, "<html>Healthy</html>")]
    [InlineData(HttpStatusCode.OK, "{\"status\":\"Healthy\",\"checks\":[]}")]
    public async Task RedirectOrInvalidPayload_CannotSatisfyReadiness(HttpStatusCode status, string body)
    {
        var handler = new SequenceHandler(new ResponseSpec(status, body));
        var clock = new ManualTimeProvider();

        var exitCode = await ReadinessProbe.RunAsync(
            Options(totalSeconds: 1),
            handler,
            clock.Delay,
            clock);

        Assert.Equal(1, exitCode);
    }

    [Fact]
    public async Task InvalidTimingBounds_AreRejectedBeforeAnyRequest()
    {
        var handler = new SequenceHandler(new ResponseSpec(HttpStatusCode.OK, Healthy));
        var invalid = Options(totalSeconds: 1) with { RequestTimeout = TimeSpan.FromSeconds(2) };

        await Assert.ThrowsAsync<ArgumentException>(() => ReadinessProbe.RunAsync(invalid, handler));
        Assert.Equal(0, handler.RequestCount);
    }

    [Fact]
    public async Task FewerThanThreeSuccesses_CannotWeakenStableReadiness()
    {
        var handler = new SequenceHandler(new ResponseSpec(HttpStatusCode.OK, Healthy));
        var invalid = Options() with { ConsecutiveSuccesses = 2 };

        await Assert.ThrowsAsync<ArgumentException>(() => ReadinessProbe.RunAsync(invalid, handler));
        Assert.Equal(0, handler.RequestCount);
    }

    [Fact]
    public async Task TotalCancellation_ReturnsControlledFailure()
    {
        using var diagnostics = new StringWriter();
        var options = Options() with
        {
            TotalTimeout = TimeSpan.FromMilliseconds(50),
            RequestTimeout = TimeSpan.FromMilliseconds(50)
        };
        var exitCode = await ReadinessProbe.RunAsync(options, new CancelledHandler(), diagnostics: diagnostics);
        Assert.Equal(1, exitCode);
        Assert.Contains("Readiness probe failed", diagnostics.ToString());
        Assert.DoesNotContain("succeeded", diagnostics.ToString());
    }

    [Theory]
    [InlineData(11, 1)]
    [InlineData(10, 1)]
    [InlineData(9, 0)]
    public async Task FinalSuccessBoundary_EnforcesElapsedDeadline(int completionSeconds, int expectedExit)
    {
        var clock = new ManualTimeProvider();
        var handler = new SequenceHandler(new ResponseSpec(HttpStatusCode.OK, Healthy))
        {
            AfterThirdBodyRead = () => clock.AdvanceTo(completionSeconds)
        };
        using var diagnostics = new StringWriter();

        var exitCode = await ReadinessProbe.RunAsync(
            Options(), handler, clock.Delay, clock, diagnostics);

        Assert.Equal(expectedExit, exitCode);
        Assert.Equal(3, handler.RequestCount);
        Assert.Equal(TimeSpan.FromSeconds(completionSeconds), clock.Elapsed);
        Assert.Equal(expectedExit == 0, diagnostics.ToString().Contains("succeeded"));
        if (expectedExit != 0)
            Assert.Contains("total readiness deadline expired", diagnostics.ToString());
    }

    [Fact]
    public async Task FinalSuccessBoundary_HonorsCancellationWithoutAnotherRead()
    {
        var clock = new ManualTimeProvider();
        var handler = new SequenceHandler(new ResponseSpec(HttpStatusCode.OK, Healthy))
        {
            AfterThirdBodyRead = clock.FireTotalTimeout
        };
        using var diagnostics = new StringWriter();

        var exitCode = await ReadinessProbe.RunAsync(
            Options(), handler, clock.Delay, clock, diagnostics);

        Assert.Equal(1, exitCode);
        Assert.Equal(3, handler.RequestCount);
        Assert.Equal(TimeSpan.FromSeconds(2), clock.Elapsed);
        Assert.Contains("total readiness deadline expired", diagnostics.ToString());
        Assert.DoesNotContain("succeeded", diagnostics.ToString());
    }

    private sealed class CancelledHandler : HttpMessageHandler
    {
        protected override async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            await Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken);
            throw new InvalidOperationException("Cancellation was not propagated.");
        }
    }

    private static ReadinessProbeOptions Options(int totalSeconds = 10, int consecutiveSuccesses = 3) =>
        new(
            TimeSpan.FromSeconds(totalSeconds),
            TimeSpan.FromSeconds(1),
            TimeSpan.FromSeconds(1),
            consecutiveSuccesses,
            4096);

    private sealed record ResponseSpec(HttpStatusCode Status, string Body);

    private sealed class SequenceHandler(params ResponseSpec[] responses) : HttpMessageHandler
    {
        private readonly Queue<ResponseSpec> _responses = new(responses);
        private ResponseSpec? _last;

        public int RequestCount { get; private set; }
        public List<string> Requests { get; } = [];
        public Action? AfterThirdBodyRead { get; init; }

        protected override Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            RequestCount++;
            Requests.Add(request.RequestUri!.AbsoluteUri);
            if (_responses.Count > 0)
            {
                _last = _responses.Dequeue();
            }

            var response = _last ?? throw new InvalidOperationException("No response configured.");
            return Task.FromResult(new HttpResponseMessage(response.Status)
            {
                Content = RequestCount == 3 && AfterThirdBodyRead is not null
                    ? new StreamContent(new FinalReadStream(response.Body, AfterThirdBodyRead))
                    : new StringContent(response.Body, Encoding.UTF8, "application/json")
            });
        }
    }

    private sealed class FinalReadStream(string body, Action afterRead)
        : MemoryStream(Encoding.UTF8.GetBytes(body))
    {
        public override async ValueTask<int> ReadAsync(
            Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            var read = await base.ReadAsync(buffer, cancellationToken);
            // Deliver time/cancellation after the last I/O check, before the
            // production parser and success accounting resume.
            if (read == 0)
                afterRead();
            return read;
        }
    }

    private sealed class ManualTimeProvider : TimeProvider
    {
        private long _timestamp;
        private ManualTimer? _totalTimer;

        public TimeSpan Elapsed => TimeSpan.FromSeconds(_timestamp);

        public override long TimestampFrequency => 1;

        public override long GetTimestamp() => _timestamp;

        // Control elapsed time and timer delivery independently to exercise
        // both a delayed timer and cancellation at the success boundary.
        public void AdvanceTo(long seconds) => _timestamp = seconds;
        public void FireTotalTimeout() => _totalTimer!.Fire();

        public override ITimer CreateTimer(TimerCallback callback, object? state,
            TimeSpan dueTime, TimeSpan period) => _totalTimer = new ManualTimer(callback, state);

        public Task Delay(TimeSpan delay, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            _timestamp += (long)delay.TotalSeconds;
            return Task.CompletedTask;
        }
    }

    private sealed class ManualTimer(TimerCallback callback, object? state) : ITimer
    {
        public void Fire() => callback(state);
        public bool Change(TimeSpan dueTime, TimeSpan period) => true;
        public void Dispose() { }
        public ValueTask DisposeAsync() => ValueTask.CompletedTask;
    }
}
