namespace terragrunt_demo.Services;

public sealed class PlaintextTooLargeException : Exception
{
    public int MaxPlaintextBytes { get; }

    public PlaintextTooLargeException(int maxPlaintextBytes)
        : base($"Plaintext must not exceed {maxPlaintextBytes} UTF-8 bytes.")
    {
        MaxPlaintextBytes = maxPlaintextBytes;
    }
}
