using MediatR;
using terragrunt_demo.Dtos;

namespace terragrunt_demo.Features.Texts.Commands
{
    public record InsertTextCommand(string Text) : IRequest<DemoTextDto>;
}
