using Microsoft.Data.SqlClient;
using Microsoft.Extensions.Configuration;
using terragrunt_demo.Data;

namespace terragrunt_demo.Tests;

public class DatabaseSecurityPolicyTests
{
    private const string Runtime = "Server=tcp:10.0.2.10,1433;Database=demo;User Id=app_runtime;Password=synthetic-test-only;Encrypt=True;TrustServerCertificate=False;HostNameInCertificate=sql.example.test";
    private const string Migrator = "Server=tcp:10.0.2.10,1433;Database=demo;User Id=app_migrator;Password=synthetic-test-only;Encrypt=True;TrustServerCertificate=False;HostNameInCertificate=sql.example.test";
    private static IConfiguration Config(params (string, string?)[] overrides)
    {
        var values = new Dictionary<string,string?> {
            ["Database:SecurityProfile"] = "validated-v2",
            ["Database:RunMigrationsOnStartup"] = "false",
            ["Database:ExpectedSqlEndpoint"] = "tcp:10.0.2.10,1433",
            ["Database:ExpectedDatabase"] = "demo",
            ["Database:ExpectedRuntimeUser"] = "app_runtime",
            ["Database:ExpectedCertificateHostName"] = "sql.example.test",
            ["DB_CONN_STRING"] = Runtime
        };
        foreach (var (key,value) in overrides) values[key]=value;
        return new ConfigurationBuilder().AddInMemoryCollection(values).Build();
    }

    [Fact] public void Strict_runtime_accepts_explicit_binding_without_changing_secret()
        => Assert.Equal(Runtime, DatabaseSecurityPolicy.RuntimeConnection(Config(), Runtime));

    [Theory]
    [InlineData("Encrypt", "False")]
    [InlineData("TrustServerCertificate", "True")]
    [InlineData("HostNameInCertificate", "other.example.test")]
    [InlineData("Data Source", "tcp:10.0.2.11,1433")]
    [InlineData("Initial Catalog", "master")]
    [InlineData("User ID", "sa")]
    [InlineData("User ID", "sa ")]
    [InlineData("Password", "")]
    [InlineData("Integrated Security", "True")]
    [InlineData("Failover Partner", "other")]
    public void Strict_runtime_rejects_tls_target_and_identity_changes(string key, string value)
    {
        var sql = new SqlConnectionStringBuilder(Runtime) { [key]=value };
        Assert.Throws<InvalidOperationException>(() => DatabaseSecurityPolicy.RuntimeConnection(Config(),sql.ConnectionString));
    }

    [Theory]
    [InlineData("Encrypt")]
    [InlineData("TrustServerCertificate")]
    public void Strict_runtime_needs_explicit_tls_fields_even_if_driver_defaults_are_safe(string field)
    {
        var sql=new SqlConnectionStringBuilder(Runtime); sql.Remove(field);
        Assert.Throws<InvalidOperationException>(() => DatabaseSecurityPolicy.RuntimeConnection(Config(),sql.ConnectionString));
    }

    [Theory]
    [InlineData("Database:ExpectedCertificateHostName", null)]
    [InlineData("Database:ExpectedCertificateHostName", "*.example.test")]
    [InlineData("Database:ExpectedDatabase", null)]
    [InlineData("Database:ExpectedRuntimeUser", null)]
    [InlineData("Database:ExpectedRuntimeUser", "sa")]
    [InlineData("Database:ExpectedRuntimeUser", "other_runtime")]
    [InlineData("Database:ExpectedSqlEndpoint", null)]
    [InlineData("Database:SecurityProfile", "typo")]
    [InlineData("Database:RunMigrationsOnStartup", "true")]
    [InlineData("DB_MIGRATION_CONN_STRING", "must-not-be-in-api-task")]
    public void Strict_runtime_rejects_missing_contract_or_unsafe_config(string key,string? value)
        => Assert.Throws<InvalidOperationException>(() => DatabaseSecurityPolicy.RuntimeConnection(Config((key,value)),Runtime));

    [Fact] public void Legacy_compatibility_is_explicit_and_not_rewritten()
        => Assert.Equal("old-test-value", DatabaseSecurityPolicy.RuntimeConnection(Config(("Database:SecurityProfile","legacy-v1")),"old-test-value"));

    [Fact] public void Migration_uses_distinct_connection_and_exact_confirmation()
        => Assert.Equal(Migrator,DatabaseSecurityPolicy.MigrationConnection(Config(("DB_MIGRATION_CONN_STRING",Migrator)),new[]{"database-migrate","--confirm-schema-change"}));

    [Fact] public void Migration_needs_no_runtime_password()
        => Assert.Equal(Migrator,DatabaseSecurityPolicy.MigrationConnection(Config(("DB_CONN_STRING",null),("DB_MIGRATION_CONN_STRING",Migrator)),new[]{"database-migrate","--confirm-schema-change"}));

    [Fact] public void Migration_has_no_runtime_fallback()
        => Assert.Throws<InvalidOperationException>(() => DatabaseSecurityPolicy.MigrationConnection(Config(),new[]{"database-migrate","--confirm-schema-change"}));

    [Fact] public void Migration_rejects_same_login()
        => Assert.Throws<InvalidOperationException>(() => DatabaseSecurityPolicy.MigrationConnection(Config(("DB_MIGRATION_CONN_STRING",Runtime)),new[]{"database-migrate","--confirm-schema-change"}));

    [Fact] public void Migration_rejects_another_database()
        => Assert.Throws<InvalidOperationException>(() => DatabaseSecurityPolicy.MigrationConnection(Config(("DB_MIGRATION_CONN_STRING",Migrator.Replace("Database=demo","Database=other"))),new[]{"database-migrate","--confirm-schema-change"}));

    [Theory]
    [InlineData("database-migrate")]
    [InlineData("database-migrate --force")]
    [InlineData("database-migrate --confirm-schema-change extra")]
    public void Migration_rejects_unsafe_arguments(string arguments)
        => Assert.Throws<InvalidOperationException>(() => DatabaseSecurityPolicy.MigrationConnection(Config(("DB_MIGRATION_CONN_STRING",Migrator)),arguments.Split(' ')));

    [Fact] public void Invalid_connection_is_sanitized()
    {
        var error=Assert.Throws<InvalidOperationException>(() => DatabaseSecurityPolicy.RuntimeConnection(Config(),"Password=synthetic-private;unsupported=x"));
        Assert.Equal("DATABASE_CONNECTION_INVALID",error.Message);
        Assert.Null(error.InnerException);
    }

    [Fact] public void Only_select_insert_pass_runtime_permission_gate()
        => RuntimeDatabasePermissions.Validate(Enumerable.Repeat<int?>(0,24).Concat(new int?[]{1,1}).ToArray());

    [Theory]
    [InlineData(0)] [InlineData(1)] [InlineData(2)] [InlineData(3)] [InlineData(4)]
    [InlineData(5)] [InlineData(6)] [InlineData(7)] [InlineData(8)] [InlineData(9)]
    [InlineData(10)] [InlineData(11)] [InlineData(12)] [InlineData(13)] [InlineData(14)]
    [InlineData(15)] [InlineData(16)] [InlineData(17)] [InlineData(18)] [InlineData(19)]
    [InlineData(20)] [InlineData(21)] [InlineData(22)] [InlineData(23)] [InlineData(24)] [InlineData(25)]
    public void Excess_or_missing_effective_permission_is_refused(int index)
    {
        var values=Enumerable.Repeat<int?>(0,24).Concat(new int?[]{1,1}).ToArray();
        values[index]= index<24 ? 1 : 0;
        Assert.Throws<InvalidOperationException>(() => RuntimeDatabasePermissions.Validate(values));
        values[index]=null;
        Assert.Throws<InvalidOperationException>(() => RuntimeDatabasePermissions.Validate(values));
    }

    [Fact] public void Startup_migrations_are_disabled_in_checked_in_defaults()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName,"demo-api","terragrunt-demo","appsettings.json"))) directory=directory.Parent;
        Assert.NotNull(directory);
        using var json=System.Text.Json.JsonDocument.Parse(File.ReadAllText(Path.Combine(directory!.FullName,"demo-api","terragrunt-demo","appsettings.json")));
        Assert.False(json.RootElement.GetProperty("Database").GetProperty("RunMigrationsOnStartup").GetBoolean());
    }

    [Fact] public void Incomplete_permission_evidence_is_refused()
        => Assert.Throws<InvalidOperationException>(() => RuntimeDatabasePermissions.Validate(Array.Empty<int?>()));
}
