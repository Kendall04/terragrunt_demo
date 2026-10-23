using SqlBackup;
using Xunit;
using System.Text.Json;

namespace SqlBackupTests;

[Collection("Process state")]
public sealed class BuildIdentityTests
{
    [Fact] public async Task BuildIdentityNeedsNoConfigOrCredentialResolution()
    {
        var original=Console.Out;using var output=new StringWriter();
        try
        {
            Console.SetOut(output);Assert.Equal(0,await Program.Main(["build-info"]));
            using var document=JsonDocument.Parse(output.ToString());var root=document.RootElement;
            Assert.Equal("SqlBackup",root.GetProperty("Component").GetString());
            Assert.Equal(3,root.EnumerateObject().Count());
            Assert.False(string.IsNullOrWhiteSpace(root.GetProperty("SourceCommit").GetString()));
        }
        finally{Console.SetOut(original);}
    }
    [Fact] public async Task BuildIdentityRejectsExtraArguments()
    {
        var original=Console.Error;using var output=new StringWriter();
        try{Console.SetError(output);Assert.Equal(1,await Program.Main(["build-info","--aws"]));Assert.Contains("INVALID_ARGUMENT",output.ToString());}
        finally{Console.SetError(original);}
    }
}
