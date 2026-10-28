using System.Data;
using System.Data.Common;
using System.Net;
using System.Net.Http.Json;
using System.Text.RegularExpressions;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Diagnostics;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using terragrunt_demo.Data;
using terragrunt_demo.Dtos;
using terragrunt_demo.Features.Texts.Queries;
using terragrunt_demo.Repositories;
using terragrunt_demo.Services;

namespace terragrunt_demo.Tests;

public class TextPaginationTests
{
    private static readonly int[] OrderedIds = { 2, 9, 8, 7, 6, 5, 4, 3, 1, 20 };
    private const string OffsetError = "Page is too large for the requested PageSize.";

    [Fact]
    public async Task Repository_ConsecutivePagesHaveStableUniqueChronologicalOrder()
    {
        using var database = new PaginationDatabase();
        // Fresh contexts ensure these assertions exercise SQL, not tracked entities.
        var ids = new List<int>();
        for (var page = 1; page <= 4; page++)
        {
            using var context = database.CreateContext();
            var repository = new DemoTextRepository(context);
            var result = await repository.GetPageAsync(page, 3);
            ids.AddRange(result.Select(item => item.Id));
            var repeated = await repository.GetPageAsync(page, 3);
            Assert.Equal(result.Select(item => item.Id), repeated.Select(item => item.Id));
        }

        Assert.Equal(OrderedIds, ids);
        Assert.Equal(OrderedIds.Length, ids.Distinct().Count());
        using var finalContext = database.CreateContext();
        Assert.Empty(await new DemoTextRepository(finalContext).GetPageAsync(5, 3));
    }

    [Theory]
    [InlineData(1, 3, 2, 9, 8)]
    [InlineData(2, 3, 7, 6, 5)]
    [InlineData(0, 3, 2, 9, 8)]
    [InlineData(int.MinValue, 3, 2, 9, 8)]
    public async Task Repository_PreservesNormalPagesAndPageNumberNormalization(
        int page, int pageSize, int first, int second, int third)
    {
        using var database = new PaginationDatabase();
        using var context = database.CreateContext();
        var result = await new DemoTextRepository(context).GetPageAsync(page, pageSize);
        Assert.Equal(new[] { first, second, third }, result.Select(item => item.Id));
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    [InlineData(int.MinValue)]
    public async Task Repository_PreservesPageSizeNormalization(int pageSize)
    {
        using var database = new PaginationDatabase();
        using var context = database.CreateContext();
        var result = await new DemoTextRepository(context).GetPageAsync(1, pageSize);
        Assert.Equal(2, Assert.Single(result).Id);
    }

    [Theory]
    [InlineData(int.MaxValue, 1)]
    [InlineData(2, int.MaxValue)] // Largest representable Skip offset.
    [InlineData(21474837, 100)] // Last valid page at the API maximum size.
    [InlineData(1, int.MaxValue)]
    public async Task Repository_AcceptsRepresentableBoundaryOffsets(int page, int pageSize)
    {
        using var database = new PaginationDatabase();
        using var context = database.CreateContext();
        var result = await new DemoTextRepository(context).GetPageAsync(page, pageSize);
        Assert.Equal(page == 1 ? OrderedIds : Array.Empty<int>(), result.Select(item => item.Id));
    }

    [Theory]
    [InlineData(21474838, 100)] // First offset above int.MaxValue.
    [InlineData(42949674, 100)] // Previously wrapped to a small positive offset.
    [InlineData(3, int.MaxValue)] // Previously wrapped negative.
    [InlineData(int.MaxValue, int.MaxValue)]
    public async Task Repository_RejectsOverflowBeforeCompilingOrOpeningDatabase(int page, int pageSize)
    {
        var interception = new OfflineSqlServerInterceptor();
        using var context = CreateSqlServerContext(interception);
        var exception = await Assert.ThrowsAsync<ArgumentOutOfRangeException>(
            () => new DemoTextRepository(context).GetPageAsync(page, pageSize));
        Assert.Equal("pageNumber", exception.ParamName);
        Assert.Contains(OffsetError, exception.Message);
        Assert.Equal(0, interception.ConnectionOpens);
        Assert.Null(interception.Sql);
    }

    [Theory]
    [InlineData(2, 3, 3)]
    [InlineData(2, int.MaxValue, int.MaxValue)]
    [InlineData(21474837, 100, 2147483600)]
    public async Task Repository_SqlServerTranslatesUniqueOrderingAndExactOffset(
        int page, int pageSize, int expectedOffset)
    {
        // Compile the actual repository query using the production provider.
        // Suppress both connection opening and execution; no SQL Server is contacted.
        var interception = new OfflineSqlServerInterceptor();
        using var context = CreateSqlServerContext(interception);
        Assert.Empty(await new DemoTextRepository(context).GetPageAsync(page, pageSize));
        Assert.Equal(1, interception.ConnectionOpens);
        Assert.NotNull(interception.Sql);
        Assert.Contains("ORDER BY [d].[CreatedAt] DESC, [d].[Id] DESC", interception.Sql);
        Assert.Contains("OFFSET @", interception.Sql);
        Assert.Contains(" ROWS FETCH NEXT @", interception.Sql);
        var bounds = Regex.Match(interception.Sql,
            @"OFFSET (@\w+) ROWS FETCH NEXT (@\w+) ROWS ONLY");
        Assert.True(bounds.Success, interception.Sql);
        Assert.Equal(expectedOffset, interception.Parameters![bounds.Groups[1].Value]);
        Assert.Equal(pageSize, interception.Parameters[bounds.Groups[2].Value]);
    }

    [Theory]
    [InlineData(0, 0, 1)]
    [InlineData(int.MinValue, int.MinValue, 1)]
    [InlineData(1, int.MaxValue, 10)]
    public async Task Handler_PreservesNormalizationAndReturnsDecryptedQueryOrder(
        int page, int pageSize, int expectedCount)
    {
        using var database = new PaginationDatabase();
        using var context = database.CreateContext();
        var handler = new GetAllTextsQueryHandler(new DemoTextRepository(context), new TestEncryption());
        var result = await handler.Handle(new GetAllTextsQuery(page, pageSize), CancellationToken.None);
        Assert.Equal(OrderedIds.Take(expectedCount), result.Select(item => item.Id));
        Assert.Equal(result.Select(item => item.Id.ToString()), result.Select(item => item.Text));
    }

    [Fact]
    public async Task Handler_CapsPageSizeBeforeCheckingOffsetAndExecutingQuery()
    {
        var interception = new OfflineSqlServerInterceptor();
        using var context = CreateSqlServerContext(interception);
        var handler = new GetAllTextsQueryHandler(new DemoTextRepository(context), new TestEncryption());
        // This page is valid at size 100, but would overflow at the raw requested size.
        Assert.Empty(await handler.Handle(
            new GetAllTextsQuery(21474837, int.MaxValue), CancellationToken.None));
        Assert.NotNull(interception.Parameters);
        Assert.Contains(100, interception.Parameters.Values);
        Assert.Contains(2147483600, interception.Parameters.Values);
    }

    [Fact]
    public async Task Handler_RejectsOverflowAfterPageSizeCapBeforeCallingRepository()
    {
        // PageSize int.MaxValue is capped to 100; this page still overflows.
        var handler = new GetAllTextsQueryHandler(new UnexpectedRepository(), new TestEncryption());
        await Assert.ThrowsAsync<ArgumentOutOfRangeException>(() => handler.Handle(
            new GetAllTextsQuery(int.MaxValue, int.MaxValue), CancellationToken.None));
    }

    [Theory]
    [InlineData("/text", 10)]
    [InlineData("/text?page=1&pageSize=3", 3)]
    [InlineData("/text?pageSize=100", 10)]
    public async Task Get_PreservesDefaultsAcceptedSizesAndDtoShape(string url, int count)
    {
        using var factory = new PaginationApiFactory();
        using var client = factory.CreateClient();
        var response = await client.GetAsync(url);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        var items = await response.Content.ReadFromJsonAsync<DemoTextDto[]>();
        Assert.NotNull(items);
        Assert.Equal(OrderedIds.Take(count), items.Select(item => item.Id));
        Assert.All(items, item =>
        {
            Assert.Equal(item.Id.ToString(), item.Text);
            Assert.NotEqual(default, item.CreatedAt);
        });
    }

    [Fact]
    public async Task Get_ConsecutivePagesKeepTiesStableWithoutMissingOrDuplicatedRecords()
    {
        using var factory = new PaginationApiFactory();
        using var client = factory.CreateClient();
        var ids = new List<int>();
        for (var page = 1; page <= 4; page++)
        {
            var items = await client.GetFromJsonAsync<DemoTextDto[]>($"/text?page={page}&pageSize=3");
            Assert.NotNull(items);
            ids.AddRange(items.Select(item => item.Id));
        }
        Assert.Equal(OrderedIds, ids);
        Assert.Equal(OrderedIds.Length, ids.Distinct().Count());
    }

    [Theory]
    [InlineData("/text?page=0", "Page must be greater than 0.")]
    [InlineData("/text?page=-2147483648", "Page must be greater than 0.")]
    [InlineData("/text?pageSize=0", "PageSize must be between 1 and 100.")]
    [InlineData("/text?pageSize=101", "PageSize must be between 1 and 100.")]
    [InlineData("/text?page=2147483647&pageSize=101", "PageSize must be between 1 and 100.")]
    [InlineData("/text?page=21474838&pageSize=100", OffsetError)]
    [InlineData("/text?page=42949674&pageSize=100", OffsetError)]
    [InlineData("/text?page=2147483647", OffsetError)]
    public async Task Get_InvalidPaginationReturnsString400BeforeRepository(string url, string error)
    {
        using var factory = new PaginationApiFactory(rejectRepositoryCalls: true);
        using var client = factory.CreateClient();
        var response = await client.GetAsync(url);
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("text/plain", response.Content.Headers.ContentType?.MediaType);
        Assert.Equal(error, await response.Content.ReadAsStringAsync());
    }

    [Theory]
    [InlineData("/text?page=2147483647&pageSize=1")]
    [InlineData("/text?page=21474837&pageSize=100")]
    public async Task Get_RepresentableBoundaryPageReturnsEmpty200(string url)
    {
        using var factory = new PaginationApiFactory();
        using var client = factory.CreateClient();
        var response = await client.GetAsync(url);
        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Empty((await response.Content.ReadFromJsonAsync<DemoTextDto[]>())!);
    }

    private static AppDbContext CreateSqlServerContext(OfflineSqlServerInterceptor interceptor) => new(
        new DbContextOptionsBuilder<AppDbContext>()
            .UseSqlServer("Server=unused.invalid;Database=unused;Integrated Security=true;")
            .AddInterceptors(interceptor)
            .Options);

    private sealed class OfflineSqlServerInterceptor : DbConnectionInterceptor, IDbCommandInterceptor
    {
        public int ConnectionOpens { get; private set; }
        public string? Sql { get; private set; }
        public Dictionary<string, int>? Parameters { get; private set; }

        public override ValueTask<InterceptionResult> ConnectionOpeningAsync(
            DbConnection connection, ConnectionEventData eventData,
            InterceptionResult result, CancellationToken cancellationToken = default)
        {
            ConnectionOpens++;
            return ValueTask.FromResult(InterceptionResult.Suppress());
        }

        public ValueTask<InterceptionResult<DbDataReader>> ReaderExecutingAsync(
            DbCommand command, CommandEventData eventData, InterceptionResult<DbDataReader> result,
            CancellationToken cancellationToken = default)
        {
            Sql = command.CommandText;
            Parameters = command.Parameters.Cast<DbParameter>()
                .ToDictionary(p => p.ParameterName, p => (int)p.Value!);
            var table = new DataTable();
            table.Columns.Add("Id", typeof(int));
            table.Columns.Add("CreatedAt", typeof(DateTime));
            table.Columns.Add("Text", typeof(string));
            return ValueTask.FromResult(InterceptionResult<DbDataReader>.SuppressWithResult(table.CreateDataReader()));
        }
    }

    private sealed class PaginationDatabase : IDisposable
    {
        private readonly SqliteConnection _connection = new("Data Source=:memory:");

        public PaginationDatabase()
        {
            _connection.Open();
            using var context = CreateContext();
            // Keep the production model/query. Only local DDL differs because
            // SQLite cannot parse SQL Server's nvarchar(max)/GETUTCDATE types/default.
            context.Database.ExecuteSqlRaw(
                "CREATE TABLE DemoTexts (Id INTEGER PRIMARY KEY, Text TEXT NOT NULL, CreatedAt TEXT NOT NULL)");
            var timestamp = new DateTime(2026, 10, 1, 0, 0, 0, DateTimeKind.Utc);
            // Insert tied IDs out of order so insertion order cannot satisfy the test.
            foreach (var id in new[] { 5, 1, 9, 3, 7, 4, 8, 6, 20, 2 })
            {
                context.DemoTexts.Add(new DemoText
                {
                    Id = id,
                    Text = $"enc:{id}",
                    CreatedAt = id == 2 ? timestamp.AddMinutes(1)
                        : id == 20 ? timestamp.AddMinutes(-1) : timestamp
                });
            }
            context.SaveChanges();
        }

        public AppDbContext CreateContext() => new(
            new DbContextOptionsBuilder<AppDbContext>().UseSqlite(_connection).Options);

        public void Dispose() => _connection.Dispose();
    }

    private sealed class PaginationApiFactory : WebApplicationFactory<Program>
    {
        private readonly PaginationDatabase _database = new();
        private readonly bool _rejectRepositoryCalls;

        public PaginationApiFactory(bool rejectRepositoryCalls = false) =>
            _rejectRepositoryCalls = rejectRepositoryCalls;

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Production");
            builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(
                new Dictionary<string, string?> { ["Database:RunMigrationsOnStartup"] = "false" }));
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<AppDbContext>();
                services.AddScoped(_ => _database.CreateContext());
                services.RemoveAll<IEncryptionService>();
                services.AddSingleton<IEncryptionService>(new TestEncryption());
                if (_rejectRepositoryCalls)
                {
                    services.RemoveAll<IDemoTextRepository>();
                    services.AddSingleton<IDemoTextRepository>(new UnexpectedRepository());
                }
            });
        }

        protected override void Dispose(bool disposing)
        {
            base.Dispose(disposing);
            if (disposing) _database.Dispose();
        }
    }

    private sealed class TestEncryption : IEncryptionService
    {
        public Task<string> EncryptAsync(string plainText, CancellationToken ct = default) =>
            throw new InvalidOperationException("Pagination must not encrypt.");

        public async Task<string> DecryptAsync(string cipherText, CancellationToken ct = default)
        {
            var plainText = cipherText[4..];
            // Different completion times must not change the returned query order.
            await Task.Delay(int.Parse(plainText) % 3, ct);
            return plainText;
        }
    }

    private sealed class UnexpectedRepository : IDemoTextRepository
    {
        public Task AddAsync(DemoText entity, CancellationToken cancellationToken = default) =>
            throw new InvalidOperationException("Invalid pagination must not access the repository.");

        public Task<IReadOnlyList<DemoText>> GetPageAsync(int pageNumber, int pageSize,
            CancellationToken cancellationToken = default) =>
            throw new InvalidOperationException("Invalid pagination must not access the repository.");
    }
}
