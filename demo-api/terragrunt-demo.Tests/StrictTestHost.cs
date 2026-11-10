using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using terragrunt_demo.Data;

namespace terragrunt_demo.Tests;

// HTTP unit tests replace the SQL I/O only. Strict configuration validation stays on.
internal static class StrictTestHost
{
    public static void Configure(IWebHostBuilder builder, bool includeConnection = true)
    {
        builder.ConfigureAppConfiguration((_, config) =>
        {
            var values = new Dictionary<string, string?> {
                ["Database:SecurityProfile"] = "validated-v2",
                ["Database:RunMigrationsOnStartup"] = "false",
                ["Database:ExpectedSqlEndpoint"] = "tcp:127.0.0.1,1433",
                ["Database:ExpectedDatabase"] = "demo",
                ["Database:ExpectedRuntimeUser"] = "app_runtime",
                ["Database:ExpectedCertificateHostName"] = "sql.example.test",
                ["DB_CONN_STRING"] = includeConnection ? "Server=tcp:127.0.0.1,1433;Database=demo;User Id=app_runtime;Password=not-a-real-password;Encrypt=True;TrustServerCertificate=False;HostNameInCertificate=sql.example.test;Connect Timeout=1;ConnectRetryCount=0" : null
            };
            config.AddInMemoryCollection(values);
        });
        builder.ConfigureServices(services =>
        {
            services.RemoveAll<IRuntimeDatabaseVerifier>();
            services.AddSingleton<IRuntimeDatabaseVerifier, NoNetworkVerifier>();
        });
    }

    private sealed class NoNetworkVerifier : IRuntimeDatabaseVerifier
    {
        public Task CheckAsync(string connection, CancellationToken cancellationToken = default) => Task.CompletedTask;
    }
}
