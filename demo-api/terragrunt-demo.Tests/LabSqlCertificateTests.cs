using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text.Json;
using Xunit.Sdk;

namespace terragrunt_demo.Tests;

// Public certificate only. CustomRootTrust stays in memory; never use a Windows store.
// Chain tests use recorded validity; the optional lab image build checks current time.
public class LabSqlCertificateTests
{
    private static string Root
    {
        get
        {
            for (var d=new DirectoryInfo(AppContext.BaseDirectory);d is not null;d=d.Parent)
                if (File.Exists(Path.Combine(d.FullName,"Dockerfile")) && File.Exists(Path.Combine(d.FullName,"terragrunt-demo.sln"))) return d.FullName;
            throw new InvalidOperationException("API source checkout required");
        }
    }
    private static string PublicPath => Path.Combine(Root,"deploy","trust","sql.demo.internal.crt");
    private static X509Certificate2 Certificate() => X509CertificateLoader.LoadCertificateFromFile(PublicPath);
    private static JsonDocument Metadata() => JsonDocument.Parse(File.ReadAllText(Path.Combine(Root,"deploy","trust","sql.demo.internal.json")));

    [Fact] public void Public_leaf_matches_recorded_fingerprint_without_private_key()
    {
        using var cert=Certificate(); using var json=Metadata(); var m=json.RootElement;
        Assert.False(cert.HasPrivateKey);
        Assert.DoesNotContain("PRIVATE KEY",File.ReadAllText(PublicPath));
        Assert.Equal(m.GetProperty("CertificateDerSha256").GetString(),Convert.ToHexString(SHA256.HashData(cert.RawData)).ToLowerInvariant());
        Assert.Equal(m.GetProperty("CertificatePemSha256").GetString(),Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(PublicPath))).ToLowerInvariant());
        Assert.False(m.GetProperty("CertificateAuthority").GetBoolean());
        Assert.False(m.GetProperty("TrustInstalledInWindows").GetBoolean());
        Assert.False(m.GetProperty("SqlHandshakeProven").GetBoolean());
        Assert.False(m.TryGetProperty("PrivateKeyPath",out _));
    }

    [Fact] public void Server_leaf_has_exact_name_purpose_and_thirty_day_lifetime()
    {
        using var cert=Certificate();
        Assert.Equal("CN=sql.demo.internal",cert.Subject);
        Assert.Equal(cert.Subject,cert.Issuer);
        Assert.True(cert.MatchesHostname("sql.demo.internal",allowWildcards:false,allowCommonName:false));
        Assert.False(cert.MatchesHostname("other.demo.internal",allowWildcards:false,allowCommonName:false));
        Assert.Equal(TimeSpan.FromDays(30),cert.NotAfter.ToUniversalTime()-cert.NotBefore.ToUniversalTime());
        Assert.False(cert.Extensions.OfType<X509BasicConstraintsExtension>().Single().CertificateAuthority);
        var usage=cert.Extensions.OfType<X509KeyUsageExtension>().Single().KeyUsages;
        Assert.True(usage.HasFlag(X509KeyUsageFlags.DigitalSignature));
        Assert.True(usage.HasFlag(X509KeyUsageFlags.KeyEncipherment));
        Assert.False(usage.HasFlag(X509KeyUsageFlags.KeyCertSign));
        var purposes=cert.Extensions.OfType<X509EnhancedKeyUsageExtension>().Single().EnhancedKeyUsages.Cast<Oid>().Select(x=>x.Value);
        Assert.Equal(new[]{"1.3.6.1.5.5.7.3.1"},purposes);
        using var rsa=cert.GetRSAPublicKey();Assert.NotNull(rsa);Assert.Equal(2048,rsa!.KeySize);
    }

    private static X509Chain Chain(X509Certificate2 certificate,bool trust,DateTime time)
    {
        var chain=new X509Chain();
        chain.ChainPolicy.TrustMode=X509ChainTrustMode.CustomRootTrust;
        if (trust) chain.ChainPolicy.CustomTrustStore.Add(certificate);
        chain.ChainPolicy.DisableCertificateDownloads=true;
        chain.ChainPolicy.RevocationMode=X509RevocationMode.NoCheck;
        chain.ChainPolicy.VerificationFlags=X509VerificationFlags.NoFlag;
        chain.ChainPolicy.VerificationTime=time;
        chain.ChainPolicy.ApplicationPolicy.Add(new Oid("1.3.6.1.5.5.7.3.1"));
        return chain;
    }

    [Fact] public void Explicit_in_memory_trust_accepts_leaf_inside_recorded_validity()
    {
        using var cert=Certificate();using var chain=Chain(cert,true,cert.NotBefore.AddMinutes(1));
        Assert.True(chain.Build(cert),string.Join(",",chain.ChainStatus.Select(x=>x.Status)));
    }

    [Fact] public void Absent_trust_is_rejected_without_network_or_store_installation()
    {
        using var cert=Certificate();using var chain=Chain(cert,false,cert.NotBefore.AddMinutes(1));
        Assert.False(chain.Build(cert));
    }

    [Fact] public void Expired_leaf_is_rejected_even_when_explicitly_trusted()
    {
        using var cert=Certificate();using var chain=Chain(cert,true,cert.NotAfter.AddMinutes(1));
        Assert.False(chain.Build(cert));
        Assert.Contains(chain.ChainStatus,x=>x.Status.HasFlag(X509ChainStatusFlags.NotTimeValid));
    }

    private static string TrustFragment(string fingerprint)
    {
        const string path="/usr/local/share/ca-certificates/ecs-sql-lab.crt";
        return "# Explicit lab-only trust. No private material or packages are installed here.\n"+
          "USER root\n"+
          $"COPY --chown=0:0 --chmod=0644 deploy/trust/sql.demo.internal.crt {path}\n"+
          $"RUN test \"$(openssl x509 -in {path} -outform DER | sha256sum | cut -d' ' -f1)\" = \"{fingerprint}\" \\\n"+
          $"    && openssl verify -CAfile {path} -purpose sslserver -verify_hostname sql.demo.internal {path} \\\n"+
          "    && update-ca-certificates\n";
    }

    private static void ValidateLabRecipe(string actual)
    {
        using var json=Metadata();var sha=json.RootElement.GetProperty("CertificateDerSha256").GetString()!;
        var normal=File.ReadAllText(Path.Combine(Root,"Dockerfile")).Replace("\r\n","\n");
        var index=normal.IndexOf("USER $APP_UID",StringComparison.Ordinal);
        var expected="# Opt-in laboratory variant. Select -f deploy/sql-lab/Dockerfile explicitly; default Dockerfile is unchanged.\n"+normal.Insert(index,TrustFragment(sha));
        Assert.Equal(expected,actual.Replace("\r\n","\n"));
    }

    [Fact] public void Lab_recipe_only_adds_reviewed_public_trust_to_exact_normal_recipe()
        => ValidateLabRecipe(File.ReadAllText(Path.Combine(Root,"deploy","sql-lab","Dockerfile")));

    [Theory]
    [InlineData("-verify_hostname sql.demo.internal","-verify_hostname other.demo.internal")]
    [InlineData("&& update-ca-certificates","&& true")]
    [InlineData("USER $APP_UID","USER root")]
    [InlineData("COPY --chown=0:0 --chmod=0644 deploy/trust/sql.demo.internal.crt","COPY private.key")]
    public void Lab_recipe_rejects_name_trust_user_and_private_material_changes(string before,string after)
    {
        var source=File.ReadAllText(Path.Combine(Root,"deploy","sql-lab","Dockerfile"));
        Assert.Contains(before,source);
        Assert.ThrowsAny<XunitException>(()=>ValidateLabRecipe(source.Replace(before,after)));
    }

    [Fact] public void Build_context_excludes_private_material_and_git_metadata()
    {
        var ignore=File.ReadAllLines(Path.Combine(Root,".dockerignore"));
        foreach (var rule in new[]{"**/.aws","**/.ssh","**/*.key","**/*.pem","**/*.pfx","**/*.p12","**/*.pkcs8","**/CodexPrivate","**/.git"}) Assert.Contains(rule,ignore);
        Assert.DoesNotContain(ignore,x=>x.StartsWith("!.git/",StringComparison.Ordinal));
        Assert.Contains("!deploy/trust/sql.demo.internal.crt",ignore);
        var gitIgnore=File.ReadAllLines(Path.Combine(Root,"..",".gitignore"));
        foreach(var rule in new[]{"*.key","*.pem","*.pfx","*.p12"}) Assert.Contains(rule,gitIgnore);
        Assert.DoesNotContain("sql.demo.internal.crt",File.ReadAllText(Path.Combine(Root,"Dockerfile")));
    }
}
