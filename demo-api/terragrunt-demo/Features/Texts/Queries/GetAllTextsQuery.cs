using MediatR;
using terragrunt_demo.Dtos;

namespace terragrunt_demo.Features.Texts.Queries
{
    public record GetAllTextsQuery(
        int PageNumber = 1,
        int PageSize = 50) : IRequest<IReadOnlyList<DemoTextDto>>;
}
