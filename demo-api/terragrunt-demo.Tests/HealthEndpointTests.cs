using System.Net;
using System.Text.Json;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Options;

namespace terragrunt_demo.Tests;

public class HealthEndpointTests
{
    [Fact]
    public async Task Health_ReturnsOk_WhenDependenciesAreUnavailable()
    {
        await using var factory = new DemoApiFactory(includeDbConnection: false);
        using var client = factory.CreateClient();

        var response = await client.GetAsync("/health");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        using var payload = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        Assert.Equal("Healthy", payload.RootElement.GetProperty("status").GetString());

        var check = Assert.Single(payload.RootElement.GetProperty("checks").EnumerateArray());
        Assert.Equal("self", check.GetProperty("name").GetString());
        Assert.Equal("Healthy", check.GetProperty("status").GetString());
    }

    [Fact]
    public async Task Ready_ReturnsServiceUnavailable_WhenDependenciesAreUnavailable()
    {
        await using var factory = new DemoApiFactory();
        using var client = factory.CreateClient();

        var response = await client.GetAsync("/ready");

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);

        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains("\"database\"", body);
        Assert.Contains("\"kms\"", body);
        Assert.DoesNotContain("not-a-real-password", body);
    }

    [Fact]
    public async Task Ready_ReturnsOk_WhenDependenciesAreAvailable()
    {
        await using var factory = new DemoApiFactory(useHealthyReadinessChecks: true);
        using var client = factory.CreateClient();

        var response = await client.GetAsync("/ready");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);

        using var payload = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        Assert.Equal("Healthy", payload.RootElement.GetProperty("status").GetString());

        var checks = payload.RootElement.GetProperty("checks").EnumerateArray().ToArray();
        Assert.Equal(2, checks.Length);
        Assert.Contains(checks, check =>
            check.GetProperty("name").GetString() == "database" &&
            check.GetProperty("status").GetString() == "Healthy");
        Assert.Contains(checks, check =>
            check.GetProperty("name").GetString() == "kms" &&
            check.GetProperty("status").GetString() == "Healthy");
    }

    [Fact]
    public async Task Swagger_IsDisabledOutsideDevelopment()
    {
        await using var factory = new DemoApiFactory(environment: "Production");
        using var client = factory.CreateClient();

        var response = await client.GetAsync("/swagger/v1/swagger.json");

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    [Fact]
    public async Task Ready_ReturnsServiceUnavailable_WhenProductionDbConnectionIsMissing()
    {
        await using var factory = new DemoApiFactory(
            environment: "Production",
            includeDbConnection: false);
        using var client = factory.CreateClient();

        var response = await client.GetAsync("/ready");

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);
        var body = await response.Content.ReadAsStringAsync();
        Assert.Contains(
            "DB_CONN_STRING must be configured outside Development",
            body);
    }

    private sealed class DemoApiFactory : WebApplicationFactory<Program>
    {
        private readonly string _environment;
        private readonly bool _includeDbConnection;
        private readonly bool _useHealthyReadinessChecks;

        public DemoApiFactory(
            string environment = "Production",
            bool includeDbConnection = true,
            bool useHealthyReadinessChecks = false)
        {
            _environment = environment;
            _includeDbConnection = includeDbConnection;
            _useHealthyReadinessChecks = useHealthyReadinessChecks;
        }

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment(_environment);
            builder.ConfigureAppConfiguration((_, config) =>
            {
                var settings = new Dictionary<string, string?>
                {
                    ["Database:RunMigrationsOnStartup"] = "false",
                    ["Database:HealthCheckTimeoutSeconds"] = "1"
                };

                if (_includeDbConnection)
                {
                    settings["DB_CONN_STRING"] = "Server=127.0.0.1,1;Database=demo;User Id=demo;Password=not-a-real-password;TrustServerCertificate=true;Connect Timeout=1;ConnectRetryCount=0;";
                }

                config.AddInMemoryCollection(settings);
            });

            if (_useHealthyReadinessChecks)
            {
                builder.ConfigureServices(services =>
                {
                    services.PostConfigure<HealthCheckServiceOptions>(options =>
                    {
                        RemoveHealthCheck(options, "database");
                        RemoveHealthCheck(options, "kms");

                        options.Registrations.Add(new HealthCheckRegistration(
                            "database",
                            new HealthyTestHealthCheck("Database connection succeeded."),
                            HealthStatus.Unhealthy,
                            new[] { "ready" }));
                        options.Registrations.Add(new HealthCheckRegistration(
                            "kms",
                            new HealthyTestHealthCheck("KMS encryption call succeeded."),
                            HealthStatus.Unhealthy,
                            new[] { "ready" }));
                    });
                });
            }
        }

        private static void RemoveHealthCheck(
            HealthCheckServiceOptions options,
            string name)
        {
            var registration = options.Registrations.Single(check => check.Name == name);
            options.Registrations.Remove(registration);
        }

        private sealed class HealthyTestHealthCheck : IHealthCheck
        {
            private readonly string _description;

            public HealthyTestHealthCheck(string description)
            {
                _description = description;
            }

            public Task<HealthCheckResult> CheckHealthAsync(
                HealthCheckContext context,
                CancellationToken cancellationToken = default)
            {
                return Task.FromResult(HealthCheckResult.Healthy(_description));
            }
        }
    }
}
