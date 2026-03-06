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

// 1) Connection string from env var (Fargate) or appsettings fallback
var configuration = builder.Configuration;

var connectionString =
    Environment.GetEnvironmentVariable("DB_CONN_STRING")
    ?? configuration.GetConnectionString("DefaultConnection")
    ?? throw new InvalidOperationException(
        "DB_CONN_STRING environment variable or DefaultConnection must be configured.");

// 2) EF Core DbContext
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseSqlServer(connectionString));

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

// 6) Health checks (DB + KMS)
builder.Services.AddHealthChecks()
    .AddDbContextCheck<AppDbContext>(
        "database",
        failureStatus: HealthStatus.Unhealthy)
    .AddCheck<KmsEncryptionHealthCheck>(
        "kms",
        failureStatus: HealthStatus.Unhealthy);

// 7) MVC / API
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

// 8) Apply migrations on startup (create DB objects if missing)
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    var logger = scope.ServiceProvider
        .GetRequiredService<ILoggerFactory>()
        .CreateLogger("StartupMigration");

    try
    {
        db.Database.Migrate();
    }
    catch (Exception ex)
    {
        logger.LogCritical(ex, "Failed to apply database migrations on startup.");
        throw;
    }
}

// 9) Middleware pipeline
app.UseSwagger();
app.UseSwaggerUI(options =>
{
    options.SwaggerEndpoint("/swagger/v1/swagger.json", "Demo API v1");
    options.RoutePrefix = string.Empty;
});


app.UseHttpsRedirection();

app.MapControllers();
app.MapHealthChecks("/health", new HealthCheckOptions
{
    Predicate = _ => true,
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
});

app.Run();
