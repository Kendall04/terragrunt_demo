using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Infrastructure;
using Microsoft.EntityFrameworkCore.Migrations;
using terragrunt_demo.Data;

namespace terragrunt_demo.Tests;

public class MigrationDiscoveryTests
{
    [Fact]
    public void ProductionSqlServerDiscoversAndScriptsCiphertextExpansionWithoutOpeningConnection()
    {
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseSqlServer("Server=127.0.0.1;Database=offline-migration-test;Integrated Security=false")
            .Options;
        using var context = new AppDbContext(options);
        Assert.Equal(new[] { "20251123201248_InitialMigration", "20260305033500_ExpandCipherTextColumn" },
            context.Database.GetMigrations());
        var script = context.GetService<IMigrator>().GenerateScript(
            "20251123201248_InitialMigration", "20260305033500_ExpandCipherTextColumn");
        Assert.Contains("ALTER TABLE [DemoTexts] ALTER COLUMN [Text] nvarchar(max) NOT NULL", script);
    }
}
