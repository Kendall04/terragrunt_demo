namespace terragrunt_demo.Features.Texts;

internal static class TextPagination
{
    public const string OffsetError = "Page is too large for the requested PageSize.";

    public static bool TryGetOffset(int pageNumber, int pageSize, out int offset)
    {
        // Skip accepts an int; widen before multiplying so overflow cannot wrap
        // an out-of-range page back into earlier records.
        var candidate = ((long)pageNumber - 1) * pageSize;
        if (candidate < 0 || candidate > int.MaxValue)
        {
            offset = 0;
            return false;
        }

        offset = (int)candidate;
        return true;
    }

    public static int GetOffset(int pageNumber, int pageSize)
    {
        if (!TryGetOffset(pageNumber, pageSize, out var offset))
            throw new ArgumentOutOfRangeException(nameof(pageNumber), OffsetError);

        return offset;
    }
}
