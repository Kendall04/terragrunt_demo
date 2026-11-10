namespace terragrunt_demo.Data;

// Dependency seam for offline HTTP tests, never a configuration bypass.
public interface IRuntimeDatabaseVerifier
{
    Task CheckAsync(string connection, CancellationToken cancellationToken = default);
}

public sealed class RuntimeDatabaseVerifier : IRuntimeDatabaseVerifier
{
    public Task CheckAsync(string connection, CancellationToken cancellationToken = default) =>
        RuntimeDatabasePermissions.CheckAsync(connection, cancellationToken);
}
