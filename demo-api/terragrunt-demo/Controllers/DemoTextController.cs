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
                return BadRequest("Text cannot be empty.1234");

            var command = new InsertTextCommand(request.Text);
            var result = await _mediator.Send(command, cancellationToken);

            return Ok(result);
        }

        // GET /text
        [HttpGet]
        public async Task<ActionResult<IReadOnlyList<DemoTextDto>>> GetAll(
            [FromQuery] int page = 1,
            [FromQuery] int pageSize = 50,
            CancellationToken cancellationToken = default)
        {
            const int maxPageSize = 100;
            if (page < 1)
                return BadRequest("Page must be greater than 0.");
            if (pageSize < 1 || pageSize > maxPageSize)
                return BadRequest($"PageSize must be between 1 and {maxPageSize}.");

            var query = new GetAllTextsQuery(page, pageSize);
            var result = await _mediator.Send(query, cancellationToken);

            return Ok(result);
        }
    }
}
