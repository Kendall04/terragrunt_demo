using MediatR;
using terragrunt_demo.Dtos;
using terragrunt_demo.Repositories;
using terragrunt_demo.Services;

namespace terragrunt_demo.Features.Texts.Queries
{
    public class GetAllTextsQueryHandler : IRequestHandler<GetAllTextsQuery, IReadOnlyList<DemoTextDto>>
    {
        private const int MaxPageSize = 100;
        private const int MaxConcurrentDecrypts = 10;

        private readonly IDemoTextRepository _repository;
        private readonly IEncryptionService _encryption;

        public GetAllTextsQueryHandler(IDemoTextRepository repository, IEncryptionService encryption)
        {
            _repository = repository;
            _encryption = encryption;
        }

        public async Task<IReadOnlyList<DemoTextDto>> Handle(GetAllTextsQuery request, CancellationToken cancellationToken)
        {
            var safePageNumber = request.PageNumber < 1 ? 1 : request.PageNumber;
            var safePageSize = request.PageSize switch
            {
                < 1 => 1,
                > MaxPageSize => MaxPageSize,
                _ => request.PageSize
            };

            var entities = await _repository.GetPageAsync(
                safePageNumber,
                safePageSize,
                cancellationToken);

            if (entities.Count == 0)
            {
                return Array.Empty<DemoTextDto>();
            }

            var maxParallelism = Math.Min(MaxConcurrentDecrypts, entities.Count);
            using var decryptThrottle = new SemaphoreSlim(maxParallelism, maxParallelism);

            var decryptTasks = entities.Select(async entity =>
            {
                await decryptThrottle.WaitAsync(cancellationToken);
                try
                {
                    var decryptedText = await _encryption.DecryptAsync(entity.Text, cancellationToken);
                    return new DemoTextDto(entity.Id, decryptedText, entity.CreatedAt);
                }
                finally
                {
                    decryptThrottle.Release();
                }
            });

            return await Task.WhenAll(decryptTasks);
        }
    }
}
