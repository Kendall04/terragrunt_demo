using Microsoft.Data.SqlClient;

namespace terragrunt_demo.Data;

public static class RuntimeDatabasePermissions
{
    // Read-only effective checks, not GRANT/REVOKE or proof of every possible permission.
    public const string InspectionSql = """
        SELECT IS_SRVROLEMEMBER('sysadmin'),
          IS_SRVROLEMEMBER('securityadmin'), IS_SRVROLEMEMBER('serveradmin'),
          IS_SRVROLEMEMBER('setupadmin'), IS_SRVROLEMEMBER('processadmin'),
          IS_SRVROLEMEMBER('diskadmin'), IS_SRVROLEMEMBER('dbcreator'),
          IS_SRVROLEMEMBER('bulkadmin'),
          HAS_PERMS_BY_NAME(NULL, 'SERVER', 'CONTROL SERVER'),
          HAS_PERMS_BY_NAME(NULL, 'SERVER', 'IMPERSONATE ANY LOGIN'),
          HAS_PERMS_BY_NAME(NULL, 'SERVER', 'ALTER ANY LOGIN'),
          HAS_PERMS_BY_NAME(NULL, 'SERVER', 'ALTER ANY SERVER ROLE'),
          IS_MEMBER('db_owner'),
          IS_MEMBER('db_ddladmin'), IS_MEMBER('db_securityadmin'),
          CASE WHEN USER_NAME() IN ('dbo','guest','sys') THEN 1 ELSE 0 END,
          HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CONTROL'),
          HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'CREATE TABLE'),
          HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'ALTER ANY USER'),
          HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'ALTER ANY ROLE'),
          HAS_PERMS_BY_NAME('dbo.DemoTexts', 'OBJECT', 'CONTROL'),
          HAS_PERMS_BY_NAME('dbo.DemoTexts', 'OBJECT', 'ALTER'),
          HAS_PERMS_BY_NAME('dbo.DemoTexts', 'OBJECT', 'UPDATE'),
          HAS_PERMS_BY_NAME('dbo.DemoTexts', 'OBJECT', 'DELETE'),
          HAS_PERMS_BY_NAME('dbo.DemoTexts', 'OBJECT', 'SELECT'),
          HAS_PERMS_BY_NAME('dbo.DemoTexts', 'OBJECT', 'INSERT');
        """;

    public static void Validate(IReadOnlyList<int?> values)
    {
        if (values.Count != 26 || values.Take(24).Any(value => value != 0) ||
            values.Skip(24).Any(value => value != 1))
            throw new InvalidOperationException("DATABASE_RUNTIME_PERMISSIONS_NOT_ADMITTED");
    }

    public static async Task CheckAsync(string connection, CancellationToken cancellationToken = default)
    {
        using var sql = new SqlConnection(connection);
        await sql.OpenAsync(cancellationToken);
        using var command = sql.CreateCommand();
        command.CommandText = InspectionSql;
        command.CommandTimeout = 15;
        using var rows = await command.ExecuteReaderAsync(cancellationToken);
        if (!await rows.ReadAsync(cancellationToken)) Validate(Array.Empty<int?>());
        var values = Enumerable.Range(0, rows.FieldCount)
            .Select(i => rows.IsDBNull(i) ? (int?)null : rows.GetInt32(i)).ToArray();
        Validate(values);
        if (await rows.ReadAsync(cancellationToken)) Validate(Array.Empty<int?>());
    }
}
