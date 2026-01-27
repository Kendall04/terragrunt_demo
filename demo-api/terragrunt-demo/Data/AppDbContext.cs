using Microsoft.EntityFrameworkCore;
using System.Collections.Generic;

namespace terragrunt_demo.Data
{
    public class AppDbContext : DbContext
    {
        public AppDbContext(DbContextOptions<AppDbContext> options)
            : base(options)
        {
        }

        public DbSet<DemoText> DemoTexts => Set<DemoText>();

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder);

            modelBuilder.Entity<DemoText>(entity =>
            {
                entity.ToTable("DemoTexts");

                entity.HasKey(x => x.Id);

                entity.Property(x => x.Text)
                    .IsRequired()
                    .HasMaxLength(1000);

                entity.Property(x => x.CreatedAt)
                    .HasDefaultValueSql("GETUTCDATE()");
            });
        }
    }
}
