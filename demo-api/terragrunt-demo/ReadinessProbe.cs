using System.Net;
using System.Text.Json;

namespace terragrunt_demo;

public sealed record ReadinessProbeOptions(
    TimeSpan TotalTimeout,
    TimeSpan RequestTimeout,
    TimeSpan PollInterval,
    int ConsecutiveSuccesses,
    int MaximumResponseBytes)
{
    public static ReadinessProbeOptions FromEnvironment()
    {
        return new ReadinessProbeOptions(
            TimeSpan.FromSeconds(ReadBoundedInt("READINESS_PROBE_TIMEOUT_SECONDS", 120, 300)),
            TimeSpan.FromSeconds(ReadBoundedInt("READINESS_PROBE_REQUEST_TIMEOUT_SECONDS", 5, 30)),
            TimeSpan.FromSeconds(ReadBoundedInt("READINESS_PROBE_INTERVAL_SECONDS", 2, 30)),
            ReadBoundedInt("READINESS_PROBE_CONSECUTIVE_SUCCESSES", 3, 10),
            ReadBoundedInt("READINESS_PROBE_MAX_RESPONSE_BYTES", 16 * 1024, 1024 * 1024));
    }

    private static int ReadBoundedInt(string name, int defaultValue, int maximumValue)
    {
        var raw = Environment.GetEnvironmentVariable(name);
        if (string.IsNullOrEmpty(raw))
        {
            return defaultValue;
        }

        if (!int.TryParse(raw, out var value) || value <= 0 || value > maximumValue)
        {
            throw new InvalidOperationException($"{name} must be between 1 and {maximumValue}.");
        }

        return value;
    }
}

public static class ReadinessProbe
{
    private static readonly Uri Endpoint = new("http://127.0.0.1:8080/ready");
    private static readonly string[] RequiredChecks = ["database", "kms"];

    public static bool IsProbeCommand(string[] args) =>
        args.Length > 0 && string.Equals(args[0], "readiness-probe", StringComparison.Ordinal);

    public static async Task<int> RunCommandAsync(string[] args)
    {
        if (args.Length == 2 && string.Equals(args[1], "--check-capability", StringComparison.Ordinal))
        {
            Console.WriteLine("readiness-probe-capability=available");
            return 0;
        }

        if (args.Length != 1)
        {
            Console.Error.WriteLine("Readiness probe received unsupported arguments.");
            return 2;
        }

        try
        {
            return await RunAsync(ReadinessProbeOptions.FromEnvironment(), diagnostics: Console.Error);
        }
        catch (Exception exception) when (exception is InvalidOperationException or ArgumentException)
        {
            Console.Error.WriteLine($"Readiness probe configuration is invalid: {exception.Message}");
            return 2;
        }
    }

    public static async Task<int> RunAsync(
        ReadinessProbeOptions options,
        HttpMessageHandler? handler = null,
        Func<TimeSpan, CancellationToken, Task>? delay = null,
        TimeProvider? timeProvider = null,
        TextWriter? diagnostics = null)
    {
        ValidateOptions(options);
        timeProvider ??= TimeProvider.System;
        delay ??= Task.Delay;
        diagnostics ??= TextWriter.Null;

        using var ownedHandler = handler is null
            ? new HttpClientHandler { AllowAutoRedirect = false, UseProxy = false }
            : null;
        using var client = new HttpClient(handler ?? ownedHandler!, disposeHandler: handler is null)
        {
            MaxResponseContentBufferSize = options.MaximumResponseBytes
        };
        using var totalCancellation = new CancellationTokenSource(options.TotalTimeout);

        var started = timeProvider.GetTimestamp();
        var streak = 0;
        var attempts = 0;
        string lastResult = "no response";

        while (timeProvider.GetElapsedTime(started) < options.TotalTimeout)
        {
            attempts++;
            try
            {
                using var requestCancellation = CancellationTokenSource.CreateLinkedTokenSource(totalCancellation.Token);
                requestCancellation.CancelAfter(options.RequestTimeout);
                using var response = await client.GetAsync(
                    Endpoint,
                    HttpCompletionOption.ResponseHeadersRead,
                    requestCancellation.Token);

                if (response.StatusCode is >= HttpStatusCode.OK and < HttpStatusCode.MultipleChoices)
                {
                    var body = await ReadBoundedBodyAsync(
                        response.Content,
                        options.MaximumResponseBytes,
                        requestCancellation.Token);
                    if (IsHealthyReadiness(body))
                    {
                        streak++;
                        lastResult = "healthy readiness response";
                        if (streak >= options.ConsecutiveSuccesses)
                        {
                            diagnostics.WriteLine($"Readiness probe succeeded after {attempts} attempt(s).");
                            return 0;
                        }
                    }
                    else
                    {
                        streak = 0;
                        lastResult = "response did not contain the required healthy checks";
                    }
                }
                else
                {
                    streak = 0;
                    lastResult = $"HTTP {(int)response.StatusCode}";
                }
            }
            catch (OperationCanceledException) when (!totalCancellation.IsCancellationRequested)
            {
                streak = 0;
                lastResult = "request timed out";
            }
            catch (Exception exception) when (exception is HttpRequestException or IOException or JsonException)
            {
                streak = 0;
                lastResult = exception.GetType().Name;
            }

            var remaining = options.TotalTimeout - timeProvider.GetElapsedTime(started);
            if (remaining <= TimeSpan.Zero || totalCancellation.IsCancellationRequested)
            {
                break;
            }

            try
            {
                await delay(
                    remaining < options.PollInterval ? remaining : options.PollInterval,
                    totalCancellation.Token);
            }
            catch (OperationCanceledException)
            {
                break;
            }
        }

        diagnostics.WriteLine(
            $"Readiness probe failed after {attempts} attempt(s): {lastResult}; " +
            $"required consecutive successes={options.ConsecutiveSuccesses}.");
        return 1;
    }

    private static void ValidateOptions(ReadinessProbeOptions options)
    {
        if (options.TotalTimeout <= TimeSpan.Zero ||
            options.RequestTimeout <= TimeSpan.Zero ||
            options.PollInterval <= TimeSpan.Zero ||
            options.ConsecutiveSuccesses <= 0 ||
            options.MaximumResponseBytes <= 0 ||
            options.RequestTimeout > options.TotalTimeout ||
            options.TotalTimeout > TimeSpan.FromMinutes(5) ||
            options.RequestTimeout > TimeSpan.FromSeconds(30) ||
            options.PollInterval > TimeSpan.FromSeconds(30) ||
            options.ConsecutiveSuccesses > 10 ||
            options.MaximumResponseBytes > 1024 * 1024)
        {
            throw new ArgumentException("All probe bounds must be positive and request timeout cannot exceed total timeout.");
        }
    }

    private static async Task<byte[]> ReadBoundedBodyAsync(
        HttpContent content,
        int maximumBytes,
        CancellationToken cancellationToken)
    {
        await using var stream = await content.ReadAsStreamAsync(cancellationToken);
        using var buffer = new MemoryStream();
        var chunk = new byte[Math.Min(4096, maximumBytes + 1)];

        while (buffer.Length <= maximumBytes)
        {
            var read = await stream.ReadAsync(chunk.AsMemory(), cancellationToken);
            if (read == 0)
            {
                return buffer.ToArray();
            }

            buffer.Write(chunk, 0, read);
        }

        throw new IOException("Readiness response exceeded the configured size bound.");
    }

    private static bool IsHealthyReadiness(byte[] body)
    {
        using var document = JsonDocument.Parse(body);
        var root = document.RootElement;
        if (root.ValueKind != JsonValueKind.Object ||
            !root.TryGetProperty("status", out var status) ||
            status.GetString() != "Healthy" ||
            !root.TryGetProperty("checks", out var checks) ||
            checks.ValueKind != JsonValueKind.Array)
        {
            return false;
        }

        foreach (var requiredName in RequiredChecks)
        {
            var matches = checks.EnumerateArray().Count(check =>
                check.ValueKind == JsonValueKind.Object &&
                check.TryGetProperty("name", out var name) &&
                name.GetString() == requiredName &&
                check.TryGetProperty("status", out var checkStatus) &&
                checkStatus.GetString() == "Healthy");
            if (matches != 1)
            {
                return false;
            }
        }

        return checks.GetArrayLength() == RequiredChecks.Length;
    }
}
