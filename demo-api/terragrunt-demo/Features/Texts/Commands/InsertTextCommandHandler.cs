using MediatR;
using terragrunt_demo.Data;
using terragrunt_demo.Dtos;
using terragrunt_demo.Repositories;
using terragrunt_demo.Services;

namespace terragrunt_demo.Features.Texts.Commands
{
    public class InsertTextCommandHandler : IRequestHandler<InsertTextCommand, DemoTextDto>
    {
        private readonly IDemoTextRepository _repository;
        private readonly IEncryptionService _encryption;

        public InsertTextCommandHandler(IDemoTextRepository repository, IEncryptionService encryption)
        {
            _repository = repository;
            _encryption = encryption;
        }

        public async Task<DemoTextDto> Handle(InsertTextCommand request, CancellationToken cancellationToken)
        {
            var encryptedText = await _encryption.EncryptAsync(request.Text, cancellationToken);

            var entity = new DemoText
            {
                Text = encryptedText,
                CreatedAt = DateTime.UtcNow
            };

            await _repository.AddAsync(entity, cancellationToken);

            return new DemoTextDto(entity.Id, request.Text, entity.CreatedAt);
        }
    }
}
