using SqlBackup;
using Xunit;
using System.Text.Json;

namespace SqlBackupTests;

[Collection("Process state")]
public sealed class ReceiptReplayTests
{
    [Theory] [InlineData("missing")] [InlineData("stale")] [InlineData("failed")]
    public async Task ReplayCheckUsesRealProtocolAndLabelsCapturedEvidence(string state)
    {
        using var lab=new Lab();var receipt=(await lab.Protocol.Backup(CancellationToken.None))!;
        if(state=="stale")receipt=receipt with {Manifest=receipt.Manifest with {StartedUtc=DateTimeOffset.UtcNow.AddHours(-3),CompletedUtc=DateTimeOffset.UtcNow.AddHours(-3).AddSeconds(1)}};
        var inputs=Path.Combine(lab.Root,"receipts.json");JsonFiles.Write(inputs,state=="missing"?Array.Empty<Receipt>():new[]{receipt});
        if(state=="failed")JsonFiles.Write(Path.Combine(lab.Options.StagingDirectory,"last-attempt.json"),new Attempt(receipt.Manifest.Id,"FAILED",DateTimeOffset.UtcNow,"BACKUP_FAILED"));
        var config=Path.Combine(lab.Root,"config.json");JsonFiles.Write(config,lab.Options);
        var original=Console.Out;using var output=new StringWriter();
        try
        {
            Console.SetOut(output);Assert.Equal(1,await Program.Main(["replay-check","--config",config,"--receipts",inputs,"--expected-up","true"]));
            using var document=JsonDocument.Parse(output.ToString());var root=document.RootElement;
            Assert.Equal("LOCAL_RECEIPT_REPLAY",root.GetProperty("Evaluation").GetString());Assert.False(root.GetProperty("RemoteStorageObserved").GetBoolean());
            Assert.Equal(state=="failed"?"FAILED":state.ToUpperInvariant(),root.GetProperty("Health").GetProperty("Status").GetString());
        }
        finally{Console.SetOut(original);}
    }
    [Fact] public async Task ReplayRejectsCloudFlagBeforeConnecting()
    {
        using var lab=new Lab();var config=Path.Combine(lab.Root,"config.json");JsonFiles.Write(config,lab.Options);var original=Console.Error;using var output=new StringWriter();
        try{Console.SetError(output);Assert.Equal(1,await Program.Main(["replay-check","--config",config,"--receipts","not-read","--expected-up","true","--aws"]));Assert.Contains("REPLAY_NO_CLOUD",output.ToString());}
        finally{Console.SetError(original);}
    }
}
