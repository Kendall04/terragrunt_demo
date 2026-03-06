using MediatR;
using Microsoft.AspNetCore.Mvc;
using terragrunt_demo.Dtos;
using terragrunt_demo.Features.Texts.Commands;
using terragrunt_demo.Features.Texts.Queries;

namespace terragrunt_demo.Controllers
{
    [ApiController]
    [Route("text")]
    public class DemoTextController : ControllerBase
    {
        private readonly IMediator _mediator;

        public DemoTextController(IMediator mediator)
        {
            _mediator = mediator;
        }

        public class InsertTextRequest
        {
            public string Text { get; set; } = string.Empty;
        }

        // POST /text 
        [HttpPost]
        public async Task<ActionResult<DemoTextDto>> InsertText(
            [FromBody] InsertTextRequest request,
            CancellationToken cancellationToken)
        {
            if (string.IsNullOrWhiteSpace(request.Text))
                return BadRequest("Text cannot be empty 2.");

            var command = new InsertTextCommand(request.Text);
            var result = await _mediator.Send(command, cancellationToken);

            return Ok(result);
        }

        // GET /text
        [HttpGet]
        public async Task<ActionResult<IReadOnlyList<DemoTextDto>>> GetAll(
            CancellationToken cancellationToken)
        {
            var query = new GetAllTextsQuery();
            var result = await _mediator.Send(query, cancellationToken);

            return Ok(result);
        }
    }
}
