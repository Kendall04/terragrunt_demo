using Microsoft.EntityFrameworkCore;
using terragrunt_demo.Data;

namespace terragrunt_demo.Tests;

public class SqlServerModelCompatibilityTests
{
    [Fact]
    public void RuntimeUpgrade_DoesNotRequireSqlServerSchemaChanges()
    {
        // Model comparison is local: this never opens a database connection.
        using var context = new AppDbContext(new DbContextOptionsBuilder<AppDbContext>()
            .UseSqlServer("Server=127.0.0.1,1;Database=offline;User Id=unused;Password=unused;Connect Timeout=1")
            .Options);

        Assert.False(context.Database.HasPendingModelChanges());
    }
}
