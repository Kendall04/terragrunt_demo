using Microsoft.Data.SqlClient;
using SqlBackup;
using Xunit;
using Xunit.Abstractions;

namespace SqlBackupTests;

public sealed class SqlExpressFactAttribute : FactAttribute
{
    public SqlExpressFactAttribute() { if (Environment.GetEnvironmentVariable("SQL_BACKUP_INTEGRATION_CONNECTION") == null) Skip = "Explicit isolated SQL Express lab and EULA authorization required"; }
}
public class SqlExpressIntegrationTests(ITestOutputHelper output)
{
    [SqlExpressFact]
    public async Task NativeExpressChecksumBackupRestoresKnownRowsAndRefusesOverwrite()
    {
        var admin = Environment.GetEnvironmentVariable("SQL_BACKUP_INTEGRATION_CONNECTION")!;
        var staging = Environment.GetEnvironmentVariable("SQL_BACKUP_INTEGRATION_STAGING") ?? throw new Exception("Isolated staging required");
        var id = Guid.NewGuid().ToString("N")[..8]; var source = "BackupLab_" + id; var target = source + "_restore_trial"; var login = "BackupOnly_" + id;
        var password = "Synthetic!" + Guid.NewGuid().ToString("N");
        var verifierLogin = "VerifyOnly_" + id; var verifierPassword = "Synthetic!" + Guid.NewGuid().ToString("N");
        await using var setup = new SqlConnection(admin); await setup.OpenAsync();
        async Task Execute(string text) { using var command = new SqlCommand(text, setup) { CommandTimeout = 120 }; await command.ExecuteNonQueryAsync(); }
        try
        {
            await Execute($"CREATE DATABASE [{source}]; ALTER DATABASE [{source}] SET RECOVERY SIMPLE; CREATE LOGIN [{login}] WITH PASSWORD='{password}',CHECK_POLICY=OFF;");
            await Execute($"USE [{source}]; CREATE TABLE dbo.DemoTexts(Id int IDENTITY PRIMARY KEY, Text nvarchar(max) NOT NULL, CreatedAt datetime2 NOT NULL DEFAULT GETUTCDATE()); INSERT dbo.DemoTexts(Text) VALUES(N'AQIDBA=='); CREATE USER [{login}] FOR LOGIN [{login}]; ALTER ROLE db_backupoperator ADD MEMBER [{login}]; USE master;");
            var limited = new SqlConnectionStringBuilder(admin) { UserID = login, Password = password, InitialCatalog = source, Pooling = false };
            await using (var permissions = new SqlConnection(limited.ConnectionString))
            {
                await permissions.OpenAsync(); using var query = new SqlCommand("SELECT IS_SRVROLEMEMBER('sysadmin'),HAS_PERMS_BY_NAME(NULL,NULL,'CREATE ANY DATABASE')", permissions);
                await using var reader = await query.ExecuteReaderAsync(); await reader.ReadAsync(); Assert.Equal(0, reader.GetInt32(0)); Assert.Equal(0, reader.GetInt32(1));
            }
            var root = Path.Combine(staging, id); Local.PrivateDirectory(root);
            var options = new Options { Database = source, StagingDirectory = Path.Combine(root, "backups"), RestoreDirectory = Path.Combine(root, "restores"), Bucket = "synthetic-integration",
                BackupKeyArn = "arn:aws:kms:us-east-1:341936017254:key/00000000-0000-0000-0000-000000000001", TextKeyArn = "arn:aws:kms:us-east-1:341936017254:key/00000000-0000-0000-0000-000000000002" };
            await Execute($"CREATE LOGIN [{verifierLogin}] WITH PASSWORD='{verifierPassword}',CHECK_POLICY=OFF; USE master; CREATE USER [{verifierLogin}] FOR LOGIN [{verifierLogin}];");
            var verifier = new SqlConnectionStringBuilder(admin) { UserID = verifierLogin, Password = verifierPassword, InitialCatalog = "master", Pooling = false };
            var preflight = Path.Combine(root, "permission-preflight.bak");
            var engine = new NativeSql(limited.ConnectionString, verifier.ConnectionString, admin, 120, allowLoopbackUntrusted: true);
            await engine.Backup(source, preflight, CancellationToken.None);
            await Assert.ThrowsAsync<SqlException>(() => engine.Verify(source, preflight, CancellationToken.None));
            await Execute($"USE master; GRANT CREATE DATABASE TO [{verifierLogin}];");
            await engine.Verify(source, preflight, CancellationToken.None);
            await using (var verifierProof = new SqlConnection(verifier.ConnectionString))
            {
                await verifierProof.OpenAsync();
                using var proof = new SqlCommand("SELECT IS_SRVROLEMEMBER('sysadmin'),IS_SRVROLEMEMBER('dbcreator'),HAS_PERMS_BY_NAME(DB_NAME(),'DATABASE','CREATE DATABASE')", verifierProof);
                await using (var rows = await proof.ExecuteReaderAsync())
                { await rows.ReadAsync(); Assert.Equal(0, rows.GetInt32(0)); Assert.Equal(0, rows.GetInt32(1)); Assert.Equal(1, rows.GetInt32(2)); }
                using var denied = new SqlCommand($"SELECT Text FROM [{source}].dbo.DemoTexts", verifierProof);
                await Assert.ThrowsAsync<SqlException>(() => denied.ExecuteScalarAsync());
            }
            output.WriteLine("VERIFIER_SYSADMIN=0 DBCREATOR=0 MASTER_CREATE_DATABASE=1; native verification succeeds; source row SELECT denied"); var store = new MemoryStore(options.BackupKeyArn); var protocol = new Protocol(options, engine, store);
            var receipt = (await protocol.Backup(CancellationToken.None))!;
            output.WriteLine("SQL_EXPRESS_VERSION=" + receipt.Manifest.SqlVersion);
            output.WriteLine("BACKUP_LOGIN_SYSADMIN=0 CREATE_ANY_DATABASE=0; native COPY_ONLY/CHECKSUM verified");
            Assert.True(receipt.Manifest.NativeChecksumVerified); Assert.StartsWith("16.", receipt.Manifest.SqlVersion);
            await Execute($"INSERT [{source}].dbo.DemoTexts(Text) VALUES(N'BQYHCA==');");
            Assert.Equal(1, await protocol.Restore(receipt.ManifestKey, receipt.ManifestVersion, target, CancellationToken.None));
            using (var read = new SqlCommand($"SELECT Text FROM [{target}].dbo.DemoTexts", setup)) Assert.Equal("AQIDBA==", await read.ExecuteScalarAsync());
            var overwrite = await Assert.ThrowsAsync<BackupFailure>(() => protocol.Restore(receipt.ManifestKey, receipt.ManifestVersion, target, CancellationToken.None)); Assert.Equal("RESTORE_DATABASE_EXISTS", overwrite.Code);
            var good = Directory.GetFiles(options.StagingDirectory, "database.bak", SearchOption.AllDirectories).Single(); var corrupt = Path.Combine(root, "truncated.bak");
            var bytes = File.ReadAllBytes(good); File.WriteAllBytes(corrupt, bytes[..(bytes.Length / 2)]);
            await Assert.ThrowsAnyAsync<Exception>(() => engine.Verify(source, corrupt, CancellationToken.None));
            using var sourceCount = new SqlCommand($"SELECT COUNT(*) FROM [{source}].dbo.DemoTexts", setup); Assert.Equal(2, (int)(await sourceCount.ExecuteScalarAsync())!);
            output.WriteLine("RESTORE_CHECKDB_AND_KNOWN_ROW=PASS; overwrite refused; truncated native backup rejected; source retained two rows");
        }
        finally
        {
            await Execute($"USE master; IF USER_ID(N'{verifierLogin}') IS NOT NULL DROP USER [{verifierLogin}]; IF SUSER_ID(N'{verifierLogin}') IS NOT NULL DROP LOGIN [{verifierLogin}]; IF DB_ID(N'{target}') IS NOT NULL BEGIN ALTER DATABASE [{target}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [{target}]; END; IF DB_ID(N'{source}') IS NOT NULL BEGIN ALTER DATABASE [{source}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE [{source}]; END; IF SUSER_ID(N'{login}') IS NOT NULL DROP LOGIN [{login}];");
        }
    }
}
