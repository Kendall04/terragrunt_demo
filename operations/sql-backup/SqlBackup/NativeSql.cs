using Microsoft.Data.SqlClient;

namespace SqlBackup;

public sealed class NativeSql(string backupConnection, string verifierConnection, string restoreConnection, int timeout, bool allowLoopbackUntrusted = false) : ISqlEngine
{
    private async Task<SqlConnection> Open(string connection, string database, CancellationToken ct)
    {
        var builder = new SqlConnectionStringBuilder(connection) { InitialCatalog = database, Encrypt = SqlConnectionEncryptOption.Mandatory };
        var host = builder.DataSource.Split(',')[0];
        if (builder.TrustServerCertificate && (!allowLoopbackUntrusted || host is not ("127.0.0.1" or "localhost" or "::1"))) throw new BackupFailure("UNTRUSTED_SQL_CERTIFICATE_DENIED");
        var result = new SqlConnection(builder.ConnectionString); await result.OpenAsync(ct); return result;
    }
    private SqlCommand Command(SqlConnection connection, string sql, params (string Name, object Value)[] parameters)
    {
        var command = new SqlCommand(sql, connection) { CommandTimeout = timeout };
        foreach (var (name, value) in parameters) command.Parameters.AddWithValue(name, value);
        return command;
    }
    public async Task<SqlInfo> Describe(string database, CancellationToken ct)
    {
        Names.Database(database);
        await using var connection = await Open(backupConnection, database, ct);
        using var command = Command(connection, "SELECT CONVERT(varchar(30),SERVERPROPERTY('ProductVersion')),CONVERT(int,SERVERPROPERTY('EngineEdition')),(SELECT SUM(CONVERT(bigint,size)*8192) FROM sys.database_files),CONVERT(varchar(30),DATABASEPROPERTYEX(DB_NAME(),'Recovery'))");
        await using var rows = await command.ExecuteReaderAsync(ct); await rows.ReadAsync(ct);
        if (rows.GetInt32(1) != 4) throw new BackupFailure("EXPRESS_EDITION_REQUIRED");
        return new(rows.GetString(0), rows.GetInt64(2), rows.GetString(3));
    }
    public async Task Backup(string database, string file, CancellationToken ct)
    {
        await using var connection = await Open(backupConnection, database, ct);
        using var command = Command(connection, $"BACKUP DATABASE {Names.Quote(database)} TO DISK=@file WITH COPY_ONLY,CHECKSUM,STOP_ON_ERROR,NO_COMPRESSION", ("@file", file));
        await command.ExecuteNonQueryAsync(ct);
    }
    public async Task Verify(string database, string file, CancellationToken ct)
    {
        await using var connection = await Open(verifierConnection, "master", ct);
        using (var command = Command(connection, "RESTORE HEADERONLY FROM DISK=@file", ("@file", file)))
        await using (var rows = await command.ExecuteReaderAsync(ct))
        {
            if (!await rows.ReadAsync(ct) || Convert.ToInt32(rows["BackupType"]) != 1 || Convert.ToInt32(rows["Position"]) != 1 ||
                (string)rows["DatabaseName"] != database || !Convert.ToBoolean(rows["HasBackupChecksums"]) || !Convert.ToBoolean(rows["IsCopyOnly"]) ||
                Convert.ToInt32(rows["SoftwareVersionMajor"]) != 16 || Convert.ToBoolean(rows["IsDamaged"]) || await rows.ReadAsync(ct))
                throw new BackupFailure("NATIVE_HEADER_REJECTED");
        }
        using var verify = Command(connection, "RESTORE VERIFYONLY FROM DISK=@file WITH CHECKSUM,STOP_ON_ERROR", ("@file", file));
        await verify.ExecuteNonQueryAsync(ct);
    }
    public async Task<long> Restore(string database, string file, string target, string directory, CancellationToken ct)
    {
        Names.Database(target);
        if (target == database || !target.StartsWith(database + "_restore_", StringComparison.Ordinal)) throw new BackupFailure("RESTORE_TARGET_DENIED");
        await using var connection = await Open(restoreConnection, "master", ct);
        using (var exists = Command(connection, "SELECT DB_ID(@target)", ("@target", target)))
            if (await exists.ExecuteScalarAsync(ct) is not DBNull) throw new BackupFailure("RESTORE_DATABASE_EXISTS");
        var files = new List<(string Logical, string Type, long Size)>();
        using (var list = Command(connection, "RESTORE FILELISTONLY FROM DISK=@file", ("@file", file)))
        await using (var rows = await list.ExecuteReaderAsync(ct))
            while (await rows.ReadAsync(ct)) files.Add(((string)rows["LogicalName"], (string)rows["Type"], Convert.ToInt64(rows["Size"])));
        if (files.Count != 2 || files.Count(f => f.Type == "D") != 1 || files.Count(f => f.Type == "L") != 1) throw new BackupFailure("UNEXPECTED_SQL_FILE_LAYOUT");
        Local.Space(directory, checked(files.Sum(f => f.Size) + 268435456));
        var data = Path.Combine(directory, "restored.mdf"); var log = Path.Combine(directory, "restored.ldf");
        if (File.Exists(data) || File.Exists(log)) throw new BackupFailure("RESTORE_FILES_EXIST");
        string Literal(string value) => "N'" + value.Replace("'", "''") + "'";
        using (var restore = Command(connection, $"RESTORE DATABASE {Names.Quote(target)} FROM DISK=@file WITH MOVE {Literal(files.Single(f => f.Type == "D").Logical)} TO @data,MOVE {Literal(files.Single(f => f.Type == "L").Logical)} TO @log,CHECKSUM,STOP_ON_ERROR,RECOVERY", ("@file", file), ("@data", data), ("@log", log)))
            await restore.ExecuteNonQueryAsync(ct); // No REPLACE, OFFLINE, DROP or source DB write.
        using (var check = Command(connection, $"DBCC CHECKDB ({Names.Quote(target)}) WITH NO_INFOMSGS,ALL_ERRORMSGS")) await check.ExecuteNonQueryAsync(ct);
        using var read = Command(connection, $"SELECT COUNT_BIG(*) FROM {Names.Quote(target)}.dbo.DemoTexts WHERE Id IS NOT NULL AND Text IS NOT NULL AND CreatedAt IS NOT NULL");
        return Convert.ToInt64(await read.ExecuteScalarAsync(ct));
    }
}
