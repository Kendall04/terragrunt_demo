using System.Text.Json;
using System.Text.RegularExpressions;
using Xunit.Sdk;

namespace terragrunt_demo.Tests;

// Offline source-contract checks. These do not replace a Linux container smoke test.
public class ContainerContractTests
{
    private static readonly string ApiRoot = FindApiRoot();
    private static readonly string Dockerfile = File.ReadAllText(Path.Combine(ApiRoot, "Dockerfile"));

    [Fact]
    public void Dockerfile_PreservesPinnedBuildAndNonRootRuntimeContract() => Validate(Dockerfile);

    [Theory]
    [InlineData("USER $APP_UID", "USER root")]
    [InlineData("USER $APP_UID", "USER 0")]
    [InlineData("USER $APP_UID", "USER app:root")]
    [InlineData("USER $APP_UID", "")]
    [InlineData("USER $APP_UID", "USER $APP_UID\nENV APP_UID=0")]
    [InlineData("EXPOSE 8080", "EXPOSE 80")]
    [InlineData("http://+:8080", "http://+:80")]
    [InlineData("FROM base AS final", "FROM build AS final")]
    [InlineData("COPY --from=build /app/publish .", "COPY --from=build /src .")]
    [InlineData("COPY --from=build /app/publish .", "COPY --from=build --chmod=600 /app/publish .")]
    [InlineData("terragrunt-demo.dll", "other.dll")]
    [InlineData("/p:UseAppHost=false", "/p:UseAppHost=true")]
    [InlineData(" --locked-mode", "")]
    [InlineData("terragrunt-demo/packages.lock.json ", "")]
    [InlineData("--no-restore", "")]
    [InlineData("&& chmod -R a+rX /app/publish", "")]
    [InlineData("a+rX", "777")]
    [InlineData("a+rX", "a+rwX")]
    [InlineData("-o /app/publish", "-o /app/other")]
    [InlineData("WORKDIR /app", "WORKDIR /root")]
    [InlineData("ENTRYPOINT", "CMD")]
    [InlineData("USER $APP_UID", "USER $APP_UID\nRUN chmod -R 777 /app")]
    public void Dockerfile_RejectsRuntimeAndOutputRegressions(string before, string after)
    {
        Assert.Contains(before, Dockerfile);
        Assert.ThrowsAny<XunitException>(() => Validate(Dockerfile.Replace(before, after)));
    }

    [Theory]
    [InlineData("aspnet")]
    [InlineData("sdk")]
    public void Dockerfile_RejectsMutableOrDifferentBaseIdentity(string family)
    {
        var pattern = $@"mcr\.microsoft\.com/dotnet/{family}:10\.0\.[0-9]+@sha256:[0-9a-f]{{64}}";
        Assert.Matches(pattern, Dockerfile);
        foreach (var replacement in new[] { $"mcr.microsoft.com/dotnet/{family}:10.0", $"mcr.microsoft.com/dotnet/{family}:9.0@sha256:{new string('0', 64)}" })
            Assert.ThrowsAny<XunitException>(() => Validate(Regex.Replace(Dockerfile, pattern, replacement)));
    }

    [Fact]
    public void EcsApplicationAndProbe_InheritImageExecutionOnLinuxX86AndPort8080()
    {
        using var task = JsonDocument.Parse(File.ReadAllText(Path.Combine(ApiRoot, "deploy", "task-definition.template.json")));
        var root = task.RootElement;
        Assert.Equal("awsvpc", root.GetProperty("networkMode").GetString());
        Assert.Equal("FARGATE", Assert.Single(root.GetProperty("requiresCompatibilities").EnumerateArray()).GetString());
        Assert.Equal("X86_64", root.GetProperty("runtimePlatform").GetProperty("cpuArchitecture").GetString());
        Assert.Equal("LINUX", root.GetProperty("runtimePlatform").GetProperty("operatingSystemFamily").GetString());
        var containers = root.GetProperty("containerDefinitions").EnumerateArray().ToArray();
        Assert.Equal(2, containers.Length);
        Assert.True(containers[0].GetProperty("essential").GetBoolean());
        var port = Assert.Single(containers[0].GetProperty("portMappings").EnumerateArray());
        Assert.Equal(8080, port.GetProperty("containerPort").GetInt32());
        Assert.Equal("tcp", port.GetProperty("protocol").GetString());
        Assert.False(containers[1].GetProperty("essential").GetBoolean());
        Assert.Equal("readiness-probe", Assert.Single(containers[1].GetProperty("command").EnumerateArray()).GetString());
        Assert.False(containers[0].TryGetProperty("command", out _));
        foreach (var container in containers)
        {
            foreach (var forbidden in new[] { "user", "entryPoint", "workingDirectory", "privileged", "mountPoints", "linuxParameters" })
                Assert.False(container.TryGetProperty(forbidden, out _), $"Unexpected execution override: {forbidden}");
            if (container.TryGetProperty("environment", out var environment))
                Assert.DoesNotContain(environment.EnumerateArray(), entry => entry.GetProperty("name").GetString() is "APP_UID" or "ASPNETCORE_URLS" or "ASPNETCORE_HTTP_PORTS");
        }
    }

    [Fact]
    public void ApplicationOutput_IsFrameworkDependentNet10WithPackagedProbe()
    {
        Assert.Contains("<TargetFramework>net10.0</TargetFramework>", File.ReadAllText(Path.Combine(ApiRoot, "terragrunt-demo", "terragrunt-demo.csproj")));
        Assert.Contains("ReadinessProbe.IsProbeCommand(args)", File.ReadAllText(Path.Combine(ApiRoot, "terragrunt-demo", "Program.cs")));
        Assert.Contains("http://127.0.0.1:8080/ready", File.ReadAllText(Path.Combine(ApiRoot, "terragrunt-demo", "ReadinessProbe.cs")));
        Assert.Equal("terragrunt-demo", typeof(Program).Assembly.GetName().Name);
    }

    private static void Validate(string source)
    {
        // Deliberately bounded grammar: admit this three-stage contract and fail on
        // added instructions (including UID overrides, remote installs or root resets).
        var normalized = Regex.Replace(source, @"\\\r?\n\s*", " ");
        var instructions = normalized.Split('\n').Select(line => line.Trim())
            .Where(line => line.Length > 0 && !line.StartsWith('#'))
            .Select(line => Regex.Replace(line, @"\s+", " ")).ToArray();
        using var evidence = JsonDocument.Parse(File.ReadAllText(Path.Combine(ApiRoot, "container-base-images.json")));
        Assert.Equal("linux/amd64", evidence.RootElement.GetProperty("platform").GetString());
        Assert.Equal(1654, evidence.RootElement.GetProperty("appUid").GetInt32());
        string Base(string stage, string family)
        {
            var image = evidence.RootElement.GetProperty("bases").GetProperty(stage);
            var tag = image.GetProperty("tag").GetString();
            var digest = image.GetProperty("manifestDigest").GetString();
            Assert.Equal($"mcr.microsoft.com/dotnet/{family}:" + (family == "sdk" ? "10.0.402" : "10.0.13"), tag);
            Assert.Matches(@"^sha256:[0-9a-f]{64}$", digest!);
            Assert.Equal("10.0.13", image.GetProperty("dotnetVersion").GetString());
            if (family == "sdk")
            {
                using var sdk = JsonDocument.Parse(File.ReadAllText(Path.Combine(ApiRoot, "..", "global.json")));
                Assert.Equal(sdk.RootElement.GetProperty("sdk").GetProperty("version").GetString(), image.GetProperty("sdkVersion").GetString());
            }
            return $"FROM {tag}@{digest} AS {stage}";
        }
        Assert.Equal(new[] {
            Base("base", "aspnet"), "WORKDIR /app", "EXPOSE 8080",
            "ENV ASPNETCORE_URLS=http://+:8080", "USER $APP_UID",
            Base("build", "sdk"), "ARG BUILD_CONFIGURATION=Release", "WORKDIR /src",
            "COPY terragrunt-demo/terragrunt-demo.csproj terragrunt-demo/packages.lock.json terragrunt-demo/",
            "RUN dotnet restore terragrunt-demo/terragrunt-demo.csproj --locked-mode",
            "COPY terragrunt-demo/ terragrunt-demo/",
            "RUN dotnet publish terragrunt-demo/terragrunt-demo.csproj -c $BUILD_CONFIGURATION --no-restore -o /app/publish /p:UseAppHost=false && chmod -R a+rX /app/publish",
            "FROM base AS final", "WORKDIR /app", "COPY --from=build /app/publish .",
            "USER $APP_UID", "ENTRYPOINT [\"dotnet\", \"terragrunt-demo.dll\"]"
        }, instructions);
    }

    private static string FindApiRoot()
    {
        for (var directory = new DirectoryInfo(AppContext.BaseDirectory); directory != null; directory = directory.Parent)
            if (File.Exists(Path.Combine(directory.FullName, "Dockerfile")) && File.Exists(Path.Combine(directory.FullName, "terragrunt-demo.sln")))
                return directory.FullName;
        throw new InvalidOperationException("Container contract tests require the demo-api source checkout.");
    }
}
