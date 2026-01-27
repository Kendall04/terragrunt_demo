using MediatR;
using terragrunt_demo.Dtos;
using terragrunt_demo.Repositories;
using terragrunt_demo.Services;

namespace terragrunt_demo.Features.Texts.Queries
{
    public class GetAllTextsQueryHandler : IRequestHandler<GetAllTextsQuery, IReadOnlyList<DemoTextDto>>
    {
        private readonly IDemoTextRepository _repository;
        private readonly IEncryptionService _encryption;

        public GetAllTextsQueryHandler(IDemoTextRepository repository, IEncryptionService encryption)
        {
            _repository = repository;
            _encryption = encryption;
        }

        public async Task<IReadOnlyList<DemoTextDto>> Handle(GetAllTextsQuery request, CancellationToken cancellationToken)
        {
            var entities = await _repository.GetAllAsync(cancellationToken);

            var result = new List<DemoTextDto>(entities.Count);

            foreach (var entity in entities)
            {
                var decryptedText = await _encryption.DecryptAsync(
                    entity.Text,
                    cancellationToken);

                result.Add(new DemoTextDto(
                    entity.Id,
                    decryptedText,
                    entity.CreatedAt));
            }

            return result;
        }
    }
}
