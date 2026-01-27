using MediatR;
using terragrunt_demo.Dtos;

namespace terragrunt_demo.Features.Texts.Queries
{
    public record GetAllTextsQuery() : IRequest<IReadOnlyList<DemoTextDto>>;
}
