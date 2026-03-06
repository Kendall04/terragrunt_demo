using terragrunt_demo.Data;
using terragrunt_demo.Features.Texts.Commands;
using terragrunt_demo.Features.Texts.Queries;
using terragrunt_demo.Repositories;
using terragrunt_demo.Services;

namespace terragrunt_demo.Tests;

public class TextHandlersTests
{
    [Fact]
    public async Task InsertTextCommandHandler_EncryptsAndPersistsCipherText()
    {
        var repository = new InMemoryDemoTextRepository();
        var encryption = new PrefixEncryptionService();
        var handler = new InsertTextCommandHandler(repository, encryption);

        var result = await handler.Handle(new InsertTextCommand("hello"), CancellationToken.None);

        Assert.Equal(1, result.Id);
        Assert.Equal("hello", result.Text);

        var saved = Assert.Single(repository.Items);
        Assert.Equal("enc:hello", saved.Text);
    }

    [Fact]
    public async Task GetAllTextsQueryHandler_DecryptsPersistedCipherText()
    {
        var repository = new InMemoryDemoTextRepository();
        repository.Seed(new DemoText
        {
            Id = 10,
            Text = "enc:stored-value",
            CreatedAt = new DateTime(2026, 3, 5, 0, 0, 0, DateTimeKind.Utc)
        });

        var encryption = new PrefixEncryptionService();
        var handler = new GetAllTextsQueryHandler(repository, encryption);

        var result = await handler.Handle(new GetAllTextsQuery(), CancellationToken.None);

        var item = Assert.Single(result);
        Assert.Equal(10, item.Id);
        Assert.Equal("stored-value", item.Text);
    }

    private sealed class InMemoryDemoTextRepository : IDemoTextRepository
    {
        private int _nextId = 1;

        public List<DemoText> Items { get; } = new();

        public Task AddAsync(DemoText entity, CancellationToken cancellationToken = default)
        {
            entity.Id = _nextId++;
            Items.Add(entity);
            return Task.CompletedTask;
        }

        public Task<IReadOnlyList<DemoText>> GetAllAsync(CancellationToken cancellationToken = default)
        {
            IReadOnlyList<DemoText> result = Items
                .OrderByDescending(item => item.CreatedAt)
                .ToList();

            return Task.FromResult(result);
        }

        public void Seed(DemoText entity)
        {
            Items.Add(entity);
        }
    }

    private sealed class PrefixEncryptionService : IEncryptionService
    {
        public Task<string> EncryptAsync(string plainText, CancellationToken ct = default)
        {
            return Task.FromResult($"enc:{plainText}");
        }

        public Task<string> DecryptAsync(string cipherText, CancellationToken ct = default)
        {
            return Task.FromResult(cipherText.Replace("enc:", string.Empty));
        }
    }
}
