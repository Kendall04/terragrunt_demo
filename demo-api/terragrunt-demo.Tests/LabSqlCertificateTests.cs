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
        return "# Explicit lab-only public trust; no private certificate material.\n"+
          $"COPY --chown=0:0 --chmod=0644 deploy/trust/sql.demo.internal.crt {path}\n"+
          $"RUN test \"$(openssl x509 -in {path} -outform DER | sha256sum | cut -d' ' -f1)\" = \"{fingerprint}\" \\\n"+
          $"    && openssl verify -CAfile {path} -purpose sslserver -verify_hostname sql.demo.internal {path} \\\n"+
          "    && update-ca-certificates\n";
    }

    private static string SecurityFragment() =>
        "# Vendor security fixes for the pinned Noble base (USN-8974-1, USN-8996-1,\n"+
        "# USN-8954-1, USN-8944-1, USN-8945-1). Exact versions fail closed if unavailable.\n"+
        "USER root\n"+
        "RUN apt-get update \\\n"+
        "    && apt-get install --no-install-recommends -y \\\n"+
        "       apt=2.8.4ubuntu0.1 libapt-pkg6.0t64=2.8.4ubuntu0.1 \\\n"+
        "       libpcre2-8-0=10.42-4ubuntu2.2 zlib1g=1:1.3.dfsg-3.1ubuntu2.3 \\\n"+
        "       ca-certificates=20260816ubuntu0.24.04.2 liblzma5=5.6.1+really5.4.5-1ubuntu0.4 \\\n"+
        "    && rm -rf /var/lib/apt/lists/*\n";

    private static void ValidateLabRecipe(string actual)
    {
        // Historical recipe admitted before the common recipe evolved. Its bytes,
        // certificate and E1 selector remain frozen, not rebased onto today's Dockerfile.
        const string pin="7efd26f2be7a80fc26d54fc3e5be44e2dcd58b4fe28b739cbd8b6adfdae8c17e";
        var normalized=actual.Replace("\r\n","\n");
        Assert.Equal(pin,Convert.ToHexString(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(normalized))).ToLowerInvariant());
        var contract=File.ReadAllText(Path.Combine(Root,"..","scripts","internal_release","e1_contract.py"));
        Assert.Contains("SQL_RECIPE_SHA256 = '"+pin+"'",contract);
        using var json=Metadata();
        Assert.Contains(SecurityFragment(),normalized);
        Assert.Contains(TrustFragment(json.RootElement.GetProperty("CertificateDerSha256").GetString()!),normalized);
    }

    [Fact] public void Historical_lab_recipe_preserves_its_exact_admitted_bytes_and_selector()
        => ValidateLabRecipe(File.ReadAllText(Path.Combine(Root,"deploy","sql-lab","Dockerfile")));

    [Theory]
    [InlineData("-verify_hostname sql.demo.internal","-verify_hostname other.demo.internal")]
    [InlineData("&& update-ca-certificates","&& true")]
    [InlineData("USER $APP_UID","USER root")]
    [InlineData("COPY --chown=0:0 --chmod=0644 deploy/trust/sql.demo.internal.crt","COPY private.key")]
    [InlineData("apt=2.8.4ubuntu0.1", "apt")]
    [InlineData("liblzma5=5.6.1+really5.4.5-1ubuntu0.4", "liblzma5=5.6.1+really5.4.5-1ubuntu0.2")]
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
