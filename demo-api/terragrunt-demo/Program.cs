using Amazon.KeyManagementService;
using MediatR;
using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using System.Text.Json;
using terragrunt_demo.Data;
using terragrunt_demo.Health;
using terragrunt_demo.Repositories;
using terragrunt_demo.Services;

var builder = WebApplication.CreateBuilder(args);

var configuration = builder.Configuration;

// 1) EF Core DbContext. ECS provides DB_CONN_STRING; local Development can use
// appsettings DefaultConnection.
builder.Services.AddDbContext<AppDbContext>((serviceProvider, options) =>
{
    var appConfiguration = serviceProvider.GetRequiredService<IConfiguration>();
    var environment = serviceProvider.GetRequiredService<IHostEnvironment>();

    options.UseSqlServer(GetRequiredConnectionString(appConfiguration, environment));
});

// 3) MediatR (CQRS)
builder.Services.AddMediatR(cfg =>
{
    cfg.RegisterServicesFromAssembly(typeof(Program).Assembly);
});

// 4) Repositories
builder.Services.AddScoped<IDemoTextRepository, DemoTextRepository>();

// 5) Services
builder.Services.AddScoped<IEncryptionService, KmsEncryptionService>();
builder.Services.AddAWSService<IAmazonKeyManagementService>();

// 6) Health checks
// CI/CD audit smoke tests keep these endpoint mappings unchanged.
builder.Services.AddHealthChecks()
    .AddCheck(
        "self",
        () => HealthCheckResult.Healthy("API process is running."),
        tags: new[] { "live" })
    .AddCheck<DatabaseConnectivityHealthCheck>(
        "database",
        failureStatus: HealthStatus.Unhealthy,
        tags: new[] { "ready" },
        timeout: TimeSpan.FromSeconds(configuration.GetValue("Database:HealthCheckTimeoutSeconds", 5)))
    .AddCheck<KmsEncryptionHealthCheck>(
        "kms",
        failureStatus: HealthStatus.Unhealthy,
        tags: new[] { "ready" },
        timeout: TimeSpan.FromSeconds(configuration.GetValue("Kms:HealthCheckTimeoutSeconds", 5)));

// 7) MVC / API
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

// 8) Apply migrations on startup when enabled. Fail fast so a task never serves
// traffic with an unknown schema state.
var runMigrationsOnStartup = configuration.GetValue("Database:RunMigrationsOnStartup", true);
if (runMigrationsOnStartup)
{
    using (var scope = app.Services.CreateScope())
    {
        var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
        var logger = scope.ServiceProvider
            .GetRequiredService<ILoggerFactory>()
            .CreateLogger("StartupMigration");

        try
        {
            logger.LogInformation("Applying database migrations on startup.");
            db.Database.Migrate();
        }
        catch (Exception ex)
        {
            logger.LogCritical(ex, "Failed to apply database migrations on startup.");
            throw;
        }
    }
}
else
{
    app.Logger.LogInformation("Database migrations on startup are disabled.");
}

// 9) Middleware pipeline
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI(options =>
    {
        options.SwaggerEndpoint("/swagger/v1/swagger.json", "Demo API v1");
        options.RoutePrefix = string.Empty;
    });

    app.UseHttpsRedirection();
}


app.MapControllers();

var liveHealthOptions = CreateHealthCheckOptions(check => check.Tags.Contains("live"));
var readyHealthOptions = CreateHealthCheckOptions(check => check.Tags.Contains("ready"));

app.MapHealthChecks("/health", liveHealthOptions);
app.MapHealthChecks("/health/live", liveHealthOptions);
app.MapHealthChecks("/ready", readyHealthOptions);
app.MapHealthChecks("/health/ready", readyHealthOptions);

app.Run();

static HealthCheckOptions CreateHealthCheckOptions(Func<HealthCheckRegistration, bool> predicate)
{
    return new HealthCheckOptions
    {
        Predicate = predicate,
        ResponseWriter = async (context, report) =>
        {
            context.Response.ContentType = "application/json";

            var payload = new
            {
                status = report.Status.ToString(),
                checks = report.Entries.Select(entry => new
                {
                    name = entry.Key,
                    status = entry.Value.Status.ToString(),
                    description = entry.Value.Description
                })
            };

            await context.Response.WriteAsync(JsonSerializer.Serialize(payload));
        }
    };
}

static string GetRequiredConnectionString(
    IConfiguration appConfiguration,
    IHostEnvironment environment)
{
    var envConnectionString = appConfiguration["DB_CONN_STRING"];
    var connectionString = !string.IsNullOrWhiteSpace(envConnectionString)
        ? envConnectionString
        : environment.IsDevelopment()
            ? appConfiguration.GetConnectionString("DefaultConnection")
            : null;

    if (string.IsNullOrWhiteSpace(connectionString))
    {
        throw new InvalidOperationException(
            "DB_CONN_STRING must be configured outside Development. In Development, DefaultConnection may be used.");
    }

    return connectionString;
}

public partial class Program
{
}
