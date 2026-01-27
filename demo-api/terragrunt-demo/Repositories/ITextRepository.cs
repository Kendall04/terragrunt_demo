using Microsoft.EntityFrameworkCore;
using terragrunt_demo.Data;

namespace terragrunt_demo.Repositories
{
    public interface IDemoTextRepository
    {
        Task AddAsync(DemoText entity, CancellationToken cancellationToken = default);
        Task<IReadOnlyList<DemoText>> GetAllAsync(CancellationToken cancellationToken = default);
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

        public async Task<IReadOnlyList<DemoText>> GetAllAsync(CancellationToken cancellationToken = default)
        {
            return await _dbContext
                .DemoTexts
                .OrderByDescending(x => x.CreatedAt)
                .ToListAsync(cancellationToken);
        }
    }
}
