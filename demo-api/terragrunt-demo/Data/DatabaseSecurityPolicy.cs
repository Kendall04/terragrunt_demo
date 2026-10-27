using Microsoft.Data.SqlClient;
using Microsoft.Extensions.Configuration;

namespace terragrunt_demo.Data;

// No certificate, credential, grant or trust-store installation occurs here.
public static class DatabaseSecurityPolicy
{
    public const string ValidatedProfile = "validated-v2";
    public static bool IsValidated(IConfiguration config)
    {
        var profile = config["Database:SecurityProfile"] ?? "legacy-v1";
        return profile switch
        {
            "legacy-v1" => false,
            ValidatedProfile => true,
            _ => throw Refuse("DATABASE_SECURITY_PROFILE_UNKNOWN")
        };
    }

    public static void ValidateStartup(IConfiguration config)
    {
        if (IsValidated(config) && config.GetValue("Database:RunMigrationsOnStartup", false))
            throw Refuse("DATABASE_RUNTIME_MIGRATION_FORBIDDEN");
    }

    public static string RuntimeConnection(IConfiguration config, string connection)
    {
        ValidateStartup(config);
        if (!IsValidated(config)) return connection;
        if (!string.IsNullOrWhiteSpace(config["DB_MIGRATION_CONN_STRING"]))
            throw Refuse("DATABASE_RUNTIME_HAS_MIGRATION_CREDENTIAL");
        var sql = ValidateConnection(config, connection);
        if (!string.Equals(sql.UserID, ExpectedRuntimeUser(config), StringComparison.OrdinalIgnoreCase))
            throw Refuse("DATABASE_RUNTIME_IDENTITY_MISMATCH");
        return connection;
    }

    public static string MigrationConnection(IConfiguration config, string[] args)
    {
        if (args.Length != 2 || args[0] != "database-migrate" || args[1] != "--confirm-schema-change")
            throw Refuse("DATABASE_MIGRATION_CONFIRMATION_REQUIRED");
        ValidateStartup(config);
        if (!IsValidated(config)) throw Refuse("DATABASE_MIGRATION_VALIDATED_PROFILE_REQUIRED");
        var runtimeUser = ExpectedRuntimeUser(config);
        var migration = ValidateConnection(config, config["DB_MIGRATION_CONN_STRING"]);
        if (string.Equals(runtimeUser, migration.UserID, StringComparison.OrdinalIgnoreCase))
            throw Refuse("DATABASE_MIGRATION_IDENTITY_NOT_SEPARATE");
        return config["DB_MIGRATION_CONN_STRING"]!;
    }

    private static string ExpectedRuntimeUser(IConfiguration config)
    {
        var user = config["Database:ExpectedRuntimeUser"];
        if (string.IsNullOrWhiteSpace(user) || user != user.Trim() ||
            string.Equals(user, "sa", StringComparison.OrdinalIgnoreCase))
            throw Refuse("DATABASE_RUNTIME_IDENTITY_REQUIRED");
        return user;
    }

    private static SqlConnectionStringBuilder ValidateConnection(IConfiguration config, string? value)
    {
        SqlConnectionStringBuilder sql;
        try { sql = new(value ?? ""); }
        catch (ArgumentException) { throw Refuse("DATABASE_CONNECTION_INVALID"); }
        var endpoint = config["Database:ExpectedSqlEndpoint"];
        var database = config["Database:ExpectedDatabase"];
        var certificateName = config["Database:ExpectedCertificateHostName"];
        if (string.IsNullOrWhiteSpace(endpoint) || string.IsNullOrWhiteSpace(database) ||
            Uri.CheckHostName(certificateName ?? "") != UriHostNameType.Dns ||
            certificateName!.Contains('*') || !certificateName.Contains('.'))
            throw Refuse("DATABASE_IDENTITY_CONTRACT_REQUIRED");
        // Explicit TLS/identity fields: no silent driver-default or pin-file substitution.
        if (!sql.ShouldSerialize("Encrypt") || sql.Encrypt != SqlConnectionEncryptOption.Mandatory ||
            !sql.ShouldSerialize("TrustServerCertificate") || sql.TrustServerCertificate ||
            !string.IsNullOrEmpty(sql.ServerCertificate) ||
            !string.Equals(sql.HostNameInCertificate, certificateName, StringComparison.OrdinalIgnoreCase))
            throw Refuse("DATABASE_TLS_VALIDATION_REQUIRED");
        var endpointHost = endpoint.StartsWith("tcp:", StringComparison.OrdinalIgnoreCase) && endpoint.EndsWith(",1433")
            ? endpoint[4..^5] : "";
        if (Uri.CheckHostName(endpointHost) == UriHostNameType.Unknown ||
            !endpoint.StartsWith("tcp:", StringComparison.OrdinalIgnoreCase) || !endpoint.EndsWith(",1433") ||
            !string.Equals(sql.DataSource, endpoint, StringComparison.OrdinalIgnoreCase) ||
            !string.Equals(sql.InitialCatalog, database, StringComparison.OrdinalIgnoreCase) ||
            new[] { "master", "tempdb", "model", "msdb" }.Contains(database, StringComparer.OrdinalIgnoreCase) ||
            sql.IntegratedSecurity || sql.Authentication != SqlAuthenticationMethod.NotSpecified ||
            sql.UserInstance || !string.IsNullOrEmpty(sql.AttachDBFilename) ||
            !string.IsNullOrEmpty(sql.FailoverPartner) || sql.UserID != sql.UserID.Trim() ||
            string.IsNullOrWhiteSpace(sql.UserID) || string.IsNullOrEmpty(sql.Password) ||
            string.Equals(sql.UserID, "sa", StringComparison.OrdinalIgnoreCase))
            throw Refuse("DATABASE_TARGET_OR_IDENTITY_INVALID");
        return sql;
    }

    private static InvalidOperationException Refuse(string code) => new(code);
}
