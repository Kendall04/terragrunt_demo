using System.Net;
using System.Net.Http.Json;
using System.Text;
using Amazon.KeyManagementService;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using terragrunt_demo.Data;
using terragrunt_demo.Dtos;
using terragrunt_demo.Repositories;

namespace terragrunt_demo.Tests;

public class TextEndpointTests
{
    [Theory]
    [MemberData(nameof(KmsEncryptionServiceTests.Boundaries), MemberType = typeof(KmsEncryptionServiceTests))]
    public async Task Post_EnforcesBoundaryBeforeEncryptionAndPersistence(string input, int byteCount)
    {
        Assert.Equal(byteCount, Encoding.UTF8.GetByteCount(input));
        await using var factory = new TextApiFactory();
        using var client = factory.CreateClient();
        var response = await client.PostAsJsonAsync("/text", new { Text = input });

        if (byteCount > 4096)
        {
            Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
            Assert.Equal("text/plain", response.Content.Headers.ContentType?.MediaType);
            Assert.Equal("Text must not exceed 4096 UTF-8 bytes.", await response.Content.ReadAsStringAsync());
            Assert.Equal(0, factory.Kms.EncryptCalls);
            Assert.Empty(factory.Repository.Items);
        }
        else
        {
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
            var dto = await response.Content.ReadFromJsonAsync<DemoTextDto>();
            Assert.NotNull(dto);
            var saved = Assert.Single(factory.Repository.Items);
            Assert.Equal(1, dto.Id);
            Assert.Equal(saved.Id, dto.Id);
            Assert.Equal(input, dto.Text);
            Assert.Equal(saved.CreatedAt, dto.CreatedAt);
            Assert.NotEqual(default, dto.CreatedAt);
            Assert.Equal(Convert.ToBase64String(RecordingKmsClient.Ciphertext), saved.Text);
            Assert.Equal(1, factory.Kms.EncryptCalls);
            Assert.Equal(Encoding.UTF8.GetBytes(input), factory.Kms.Plaintext);
            Assert.Equal("test-key", factory.Kms.KeyId);
            Assert.Equal(factory.Repository.Token, factory.Kms.Token);
        }
    }

    [Theory]
    [InlineData(0)]
    [InlineData(4097)]
    public async Task Post_BlankValidationTakesPrecedence(int length)
    {
        await using var factory = new TextApiFactory();
        using var client = factory.CreateClient();
        var response = await client.PostAsJsonAsync("/text", new { Text = new string(' ', length) });
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        Assert.Equal("Text cannot be empty.1234", await response.Content.ReadAsStringAsync());
        Assert.Equal(0, factory.Kms.EncryptCalls);
        Assert.Empty(factory.Repository.Items);
    }

    private sealed class TextApiFactory : WebApplicationFactory<Program>
    {
        public RecordingKmsClient Kms { get; } = new();
        public RecordingRepository Repository { get; } = new();

        protected override void ConfigureWebHost(IWebHostBuilder builder)
        {
            builder.UseEnvironment("Production");
            builder.ConfigureAppConfiguration((_, config) => config.AddInMemoryCollection(
                new Dictionary<string, string?>
                {
                    ["Database:RunMigrationsOnStartup"] = "false",
                    ["KMS_KEY_ID"] = "test-key"
                }));
            builder.ConfigureServices(services =>
            {
                services.RemoveAll<IAmazonKeyManagementService>();
                services.AddSingleton<IAmazonKeyManagementService>(Kms);
                services.RemoveAll<IDemoTextRepository>();
                services.AddSingleton<IDemoTextRepository>(Repository);
            });
        }
    }

    private sealed class RecordingRepository : IDemoTextRepository
    {
        public List<DemoText> Items { get; } = new();
        public CancellationToken Token { get; private set; }

        public Task AddAsync(DemoText entity, CancellationToken cancellationToken = default)
        {
            Token = cancellationToken;
            entity.Id = 1;
            Items.Add(entity);
            return Task.CompletedTask;
        }

        public Task<IReadOnlyList<DemoText>> GetPageAsync(int pageNumber, int pageSize,
            CancellationToken cancellationToken = default) => throw new NotSupportedException();
    }
}
