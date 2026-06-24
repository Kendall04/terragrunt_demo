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
        Assert.Equal(1, repository.LastPageNumber);
        Assert.Equal(50, repository.LastPageSize);
    }

    [Fact]
    public async Task GetAllTextsQueryHandler_AppliesPagination()
    {
        var repository = new InMemoryDemoTextRepository();
        repository.Seed(new DemoText
        {
            Id = 1,
            Text = "enc:first",
            CreatedAt = new DateTime(2026, 3, 5, 3, 0, 0, DateTimeKind.Utc)
        });
        repository.Seed(new DemoText
        {
            Id = 2,
            Text = "enc:second",
            CreatedAt = new DateTime(2026, 3, 5, 2, 0, 0, DateTimeKind.Utc)
        });
        repository.Seed(new DemoText
        {
            Id = 3,
            Text = "enc:third",
            CreatedAt = new DateTime(2026, 3, 5, 1, 0, 0, DateTimeKind.Utc)
        });

        var encryption = new PrefixEncryptionService();
        var handler = new GetAllTextsQueryHandler(repository, encryption);

        var result = await handler.Handle(
            new GetAllTextsQuery(PageNumber: 2, PageSize: 1),
            CancellationToken.None);

        var item = Assert.Single(result);
        Assert.Equal(2, item.Id);
        Assert.Equal("second", item.Text);
        Assert.Equal(2, repository.LastPageNumber);
        Assert.Equal(1, repository.LastPageSize);
    }

    private sealed class InMemoryDemoTextRepository : IDemoTextRepository
    {
        private int _nextId = 1;

        public List<DemoText> Items { get; } = new();
        public int LastPageNumber { get; private set; } = 1;
        public int LastPageSize { get; private set; } = 50;

        public Task AddAsync(DemoText entity, CancellationToken cancellationToken = default)
        {
            entity.Id = _nextId++;
            Items.Add(entity);
            return Task.CompletedTask;
        }

        public Task<IReadOnlyList<DemoText>> GetPageAsync(
            int pageNumber,
            int pageSize,
            CancellationToken cancellationToken = default)
        {
            LastPageNumber = pageNumber;
            LastPageSize = pageSize;

            var safePageNumber = pageNumber < 1 ? 1 : pageNumber;
            var safePageSize = pageSize < 1 ? 1 : pageSize;
            var skip = (safePageNumber - 1) * safePageSize;

            IReadOnlyList<DemoText> result = Items
                .OrderByDescending(item => item.CreatedAt)
                .Skip(skip)
                .Take(safePageSize)
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
