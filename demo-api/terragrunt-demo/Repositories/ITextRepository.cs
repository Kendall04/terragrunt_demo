using Microsoft.EntityFrameworkCore;
using terragrunt_demo.Data;

namespace terragrunt_demo.Repositories
{
    public interface IDemoTextRepository
    {
        Task AddAsync(DemoText entity, CancellationToken cancellationToken = default);
        Task<IReadOnlyList<DemoText>> GetPageAsync(
            int pageNumber,
            int pageSize,
            CancellationToken cancellationToken = default);
    }

    public class DemoTextRepository : IDemoTextRepository
    {
        private readonly AppDbContext _dbContext;

        public DemoTextRepository(AppDbContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task AddAsync(DemoText entity, CancellationToken cancellationToken = default)
        {
            await _dbContext.DemoTexts.AddAsync(entity, cancellationToken);
            await _dbContext.SaveChangesAsync(cancellationToken);
        }

        public async Task<IReadOnlyList<DemoText>> GetPageAsync(
            int pageNumber,
            int pageSize,
            CancellationToken cancellationToken = default)
        {
            var safePageNumber = pageNumber < 1 ? 1 : pageNumber;
            var safePageSize = pageSize < 1 ? 1 : pageSize;
            var skip = (safePageNumber - 1) * safePageSize;

            return await _dbContext
                .DemoTexts
                .OrderByDescending(x => x.CreatedAt)
                .Skip(skip)
                .Take(safePageSize)
                .ToListAsync(cancellationToken);
        }
    }
}
