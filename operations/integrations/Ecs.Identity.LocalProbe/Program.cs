using System.Diagnostics;
using System.Reflection;
using System.Net;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Authentication;
using System.Security.Claims;
using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.Json;
using Ecs.Identity;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using ServiceIdentity.Pki.Core;
using ServiceIdentity.Pki.Providers.Local;
using ServiceIdentity.Pki.Integration.AspNetCore;

if(args is ["--anonymous-no-key"]) { await AnonymousNoKey();return; }

var checks=new List<string>();var failures=new List<string>();var observations=new List<object>();
void Check(string name,bool value) { checks.Add(name);if(!value)failures.Add(name); }
var clock=new ServiceIdentity.Pki.Core.SystemClock();
using var enrollment=new LocalEnrollmentAuthority(clock);using var ca=LocalCertificateAuthority.Create(enrollment,clock);
using var foreignEnrollment=new LocalEnrollmentAuthority(clock);using var foreign=LocalCertificateAuthority.Create(foreignEnrollment,clock);
var material=new List<X509Certificate2>();
async Task<X509Certificate2> Issue(string service,CertificatePurpose purpose,bool untrusted=false) {
    using var key=LocalKeyPair.Create();
    var profile=service=="intruder"?new CertificateProfile(new ServiceId("ecs-demo.example","local-development","intruder"),purpose):EcsDevelopmentIdentity.Profile(service,purpose);
    var request=key.CreateRequest(profile,clock.UtcNow.AddSeconds(-30),TimeSpan.FromMinutes(5));
    var grant=(untrusted?foreignEnrollment:enrollment).Grant(profile,TimeSpan.FromMinutes(10),clock.UtcNow.AddMinutes(10));
    var issued=await (untrusted?foreign:ca).IssueAsync(request,grant);
    var certificate=key.AttachCertificate(issued.Certificate);material.Add(certificate);return certificate;
}
var apps=new List<WebApplication>();
try {
 async Task<(WebApplication App,int Port,ServiceIdentityPkiRuntime Runtime)> Start(string name) {
    var server=await Issue(name,CertificatePurpose.Server);var client=await Issue(name,CertificatePurpose.Client);
    var b=WebApplication.CreateSlimBuilder(new WebApplicationOptions { Args=[],EnvironmentName="Development" });
    b.Configuration.Sources.Clear();b.Logging.ClearProviders();
    b.Services.AddSingleton<IClock>(clock);b.Services.AddSingleton<ICertificateValidator,X509CertificateValidator>();
    b.Services.AddEcsDevelopmentIdentity(name,ca.Root,ca.Intermediate,server,client);
    b.WebHost.UseServiceIdentityPkiEndpoint(IPAddress.Loopback,0);
    var app=b.Build();apps.Add(app);app.UseAuthentication();app.UseAuthorization();
    app.MapGet("/identity",(HttpContext context)=>Results.Json(new { Identity=context.User.FindFirstValue(ClaimTypes.NameIdentifier),ClientFingerprint=context.User.FindFirstValue("certificate-fingerprint"),ServerObservedClientFingerprint=context.Connection.ClientCertificate is null?null:Convert.ToHexString(SHA256.HashData(context.Connection.ClientCertificate.RawData)).ToLowerInvariant(),ConnectionId=context.Connection.Id,RemotePort=context.Connection.RemotePort })).RequireAuthorization(EcsDevelopmentIdentity.Read);
    app.MapGet("/observe",()=>Results.Ok(new { Scope="LOCAL_TEST_ONLY" })).RequireAuthorization(EcsDevelopmentIdentity.Observe);
    await app.StartAsync();
    var address=app.Services.GetRequiredService<IServer>().Features.Get<IServerAddressesFeature>()!.Addresses.Single();
    return(app,new Uri(address).Port,app.Services.GetRequiredService<ServiceIdentityPkiRuntime>());
 }
 var a=await Start("text-api");var b=await Start("recovery-observer");
 Check("two loopback Kestrel hosts",a.Port!=b.Port && a.Port>0 && b.Port>0);
 async Task<int> Call(ServiceIdentityPkiRuntime caller,string target,int port,string path,string? forged=null) {
    using var client=caller.OpenClient(EcsDevelopmentIdentity.Profile(target,CertificatePurpose.Server));
    client.Http.Timeout=TimeSpan.FromSeconds(10); // Local qualification allowance; TLS validation/handshake bounds unchanged.
    using var request=new HttpRequestMessage(HttpMethod.Get,$"https://localhost:{port}/{path}");
    if(forged is not null)request.Headers.Add("X-Service-Identity",forged);
    using var response=await client.Http.SendAsync(request);return(int)response.StatusCode;
 }
 Check("text-api to observer authentic mTLS",await Call(a.Runtime,"recovery-observer",b.Port,"identity")==200);
 Check("observer to text-api authentic mTLS",await Call(b.Runtime,"text-api",a.Port,"identity")==200);
 Check("authorized observer operation",await Call(b.Runtime,"text-api",a.Port,"observe")==200);
 Check("text-api cannot elevate",await Call(a.Runtime,"text-api",a.Port,"observe")==403);
 Check("forged header cannot elevate",await Call(a.Runtime,"text-api",a.Port,"observe",EcsDevelopmentIdentity.Id("recovery-observer").Uri)==403);

 async Task<(int Status,string Body,string Fingerprint)> Fresh(int port,string expectedServer,X509Certificate2? clientCertificate,string expectedDns="localhost",CertificateData? clientIntermediate=null) {
    using var timeout=new CancellationTokenSource(TimeSpan.FromSeconds(8));
    using var trust=new PeerTrust(new X509CertificateValidator(clock),TrustPolicy.ForLocalDevelopment(ca.Root),[new(EcsDevelopmentIdentity.Id(expectedServer),CertificatePurpose.Server,expectedDns)]);
    using var tcp=new TcpClient();await tcp.ConnectAsync(IPAddress.Loopback,port,timeout.Token);
    string? fingerprint=null;
    await using var tls=new SslStream(tcp.GetStream(),false,(_,remote,chain,errors)=>{
      if(trust.Validate(remote,chain,errors) is null)return false;
      fingerprint=Convert.ToHexString(SHA256.HashData(remote!.GetRawCertData())).ToLowerInvariant();return true;
    });
    using var intermediate=X509CertificateLoader.LoadCertificate((clientIntermediate??ca.Intermediate).ExportDer());
    byte[]? pfx=clientCertificate?.Export(X509ContentType.Pkcs12);
    X509Certificate2? nativeClient=null;
    try { if(pfx is not null)nativeClient=TlsCredentialImport.Import(pfx); }
    finally { if(pfx is not null)CryptographicOperations.ZeroMemory(pfx); }
    using var importedClient=nativeClient;
    var options=new SslClientAuthenticationOptions { TargetHost=expectedDns,EnabledSslProtocols=SslProtocols.Tls12|SslProtocols.Tls13,AllowTlsResume=false,CertificateChainPolicy=trust.CreateChainPolicy(CertificatePurpose.Server),ClientCertificateContext=importedClient is null?null:SslStreamCertificateContext.Create(importedClient,new X509Certificate2Collection(intermediate),true) };
    if(clientCertificate is null) { options.ClientCertificates=new X509CertificateCollection();options.LocalCertificateSelectionCallback=(_,_,_,_,_)=>null!; }
    await tls.AuthenticateAsClientAsync(options,timeout.Token);
    observations.Add(new { Scenario="native-client-credential",RequestedClientCertificate=clientCertificate is not null,PresentedClientFingerprint=tls.LocalCertificate is null?null:Convert.ToHexString(SHA256.HashData(tls.LocalCertificate.GetRawCertData())).ToLowerInvariant(),tls.IsMutuallyAuthenticated });
    await tls.WriteAsync(Encoding.ASCII.GetBytes("GET /identity HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"),timeout.Token);
    using var reader=new StreamReader(tls);var text=await reader.ReadToEndAsync(timeout.Token);
    if(!text.StartsWith("HTTP/1.1 ")||fingerprint is null)throw new AuthenticationException("TLS_PEER_REJECTED");
    observations.Add(new { Scenario="native-peer-after-request",RequestedClientCertificate=clientCertificate is not null,PresentedClientFingerprint=tls.LocalCertificate is null?null:Convert.ToHexString(SHA256.HashData(tls.LocalCertificate.GetRawCertData())).ToLowerInvariant(),tls.IsMutuallyAuthenticated,HttpStatus=int.Parse(text.Split(' ')[1]),ClientLocalPort=((IPEndPoint)tcp.Client.LocalEndPoint!).Port,SyntheticResponseBody=text[(text.IndexOf("\r\n\r\n",StringComparison.Ordinal)+4)..] });
    return(int.Parse(text.Split(' ')[1]),text,fingerprint);
 }
 async Task Reject(string name,Func<Task<(int Status,string Body,string Fingerprint)>> operation) {
    var rejected=false;string boundary="TLS_OR_IO";
    try { var response=await operation();rejected=response.Status is 401 or 403;boundary="HTTP_"+response.Status; }
    catch(Exception e)when(e is AuthenticationException or HttpRequestException or IOException or SocketException){rejected=true;}
    observations.Add(new { Scenario=name,RejectionBoundary=boundary,Rejected=rejected });
    Check(name,rejected);
 }
 var observerClient=await Issue("recovery-observer",CertificatePurpose.Client);
 var initial=await Fresh(a.Port,"text-api",observerClient);
 Check("fresh TLS observes initial server fingerprint",initial.Status==200 && initial.Fingerprint==a.Runtime.Generations.Current.ServerFingerprint);
 Check("server derives peer identity from certificate",initial.Body.Contains(EcsDevelopmentIdentity.Id("recovery-observer").Uri) && initial.Body.Contains(Convert.ToHexString(SHA256.HashData(observerClient.RawData)).ToLowerInvariant()));
 observations.Add(new { Generation="initial",ObservedServerFingerprint=initial.Fingerprint,ExpectedServerFingerprint=a.Runtime.Generations.Current.ServerFingerprint });
 // Same-process unspecified credentials were not a proven anonymous connection. Preserve the diagnostic and observe server-side certificate evidence.
 try { var sameProcess=await Fresh(a.Port,"text-api",null);
 observations.Add(new { Scenario="same-process-unspecified-client",sameProcess.Status,ResponseNamesExistingTextApiCredential=sameProcess.Body.Contains(a.Runtime.Generations.Current.ClientFingerprint) }); }
 catch(Exception e)when(e is AuthenticationException or IOException) { observations.Add(new { Scenario="same-process-unspecified-client",RejectionBoundary="TLS_OR_IO" }); }
 var start=new ProcessStartInfo(Environment.ProcessPath!) { RedirectStandardInput=true,RedirectStandardOutput=true,RedirectStandardError=true,UseShellExecute=false,CreateNoWindow=true };
 start.ArgumentList.Add(Assembly.GetExecutingAssembly().Location);start.ArgumentList.Add("--anonymous-no-key");
 var allowed=new[]{"SystemRoot","WINDIR","TEMP","TMP"};var childEnvironment=allowed.Where(start.Environment.ContainsKey).ToDictionary(n=>n,n=>start.Environment[n]);
 start.Environment.Clear();foreach(var pair in childEnvironment)start.Environment[pair.Key]=pair.Value;
 start.Environment["DOTNET_CLI_TELEMETRY_OPTOUT"]="1";start.Environment["DOTNET_SKIP_FIRST_TIME_EXPERIENCE"]="1";start.Environment["DOTNET_GENERATE_ASPNET_CERTIFICATE"]="false";
 using(var child=Process.Start(start)??throw new InvalidOperationException("ANONYMOUS_CHILD_START")) {
    var output=child.StandardOutput.ReadToEndAsync();var errors=child.StandardError.ReadToEndAsync();
    await child.StandardInput.WriteLineAsync(JsonSerializer.Serialize(new { a.Port,Root=ca.Root.ExportDer() }));child.StandardInput.Close();
    await child.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(15));
    using var receipt=JsonDocument.Parse(await output);await errors;
    observations.Add(new { Scenario="independent-no-key-client",Receipt=receipt.RootElement.Clone(),child.ExitCode });
    Check("independent client without private material rejected",child.ExitCode==0 && receipt.RootElement.GetProperty("Rejected").GetBoolean());
 }

 var untrusted=await Issue("recovery-observer",CertificatePurpose.Client,true);
 await Reject("foreign CA client rejected",()=>Fresh(a.Port,"text-api",untrusted,clientIntermediate:foreign.Intermediate));
 var intruder=await Issue("intruder",CertificatePurpose.Client);
 await Reject("unknown identity rejected",()=>Fresh(a.Port,"text-api",intruder));
 await Reject("wrong expected server identity rejected",()=>Fresh(a.Port,"recovery-observer",observerClient));
 await Reject("wrong DNS rejected",()=>Fresh(a.Port,"text-api",observerClient,"wrong.example"));

 using var oldClient=a.Runtime.OpenClient(EcsDevelopmentIdentity.Profile("recovery-observer",CertificatePurpose.Server));
 using(var response=await oldClient.Http.GetAsync($"https://localhost:{b.Port}/identity"))Check("old generation acquired before replacement",(int)response.StatusCode==200);
 var prior=a.Runtime.Generations.Current;
 var nextServer=await Issue("text-api",CertificatePurpose.Server);var nextClient=await Issue("text-api",CertificatePurpose.Client);
 using(var prepared=a.Runtime.Generations.Prepare("rotated",nextServer,nextClient,ca.Intermediate)) {
   var conflict=false;try{a.Runtime.Generations.Activate(prepared,prior.Sequence+1);}catch(ReplacementException e)when(e.Code=="Conflict"){conflict=true;}
   Check("stale sequence rejected without activation",conflict && a.Runtime.Generations.Current==prior);
   a.Runtime.Generations.Activate(prepared,prior.Sequence);
 }
 var current=a.Runtime.Generations.Current;
 Check("rotation changes both certificate fingerprints",current.Sequence==prior.Sequence+1 && current.ServerFingerprint!=prior.ServerFingerprint && current.ClientFingerprint!=prior.ClientFingerprint);
 var rotated=await Fresh(a.Port,"text-api",observerClient);
 Check("new handshake observes rotated server certificate",rotated.Status==200 && rotated.Fingerprint==current.ServerFingerprint && rotated.Fingerprint!=initial.Fingerprint);
 observations.Add(new { Generation="rotated",ObservedServerFingerprint=rotated.Fingerprint,ExpectedServerFingerprint=current.ServerFingerprint });
 using(var newCaller=a.Runtime.OpenClient(EcsDevelopmentIdentity.Profile("recovery-observer",CertificatePurpose.Server))) {
   var body=await newCaller.Http.GetStringAsync($"https://localhost:{b.Port}/identity");
   Check("new outgoing connection uses rotated client certificate",body.Contains(current.ClientFingerprint));
 }
 var invalid=false;try{using var _=a.Runtime.Generations.Prepare("invalid",await Issue("recovery-observer",CertificatePurpose.Server),nextClient,ca.Intermediate);}catch(ReplacementException){invalid=true;}
 Check("wrong identity replacement leaves current generation intact",invalid && a.Runtime.Generations.Current==current);
 await Task.Delay(650);
 var drained=false;try{using var response=await oldClient.Http.GetAsync($"https://localhost:{b.Port}/identity");}catch(ReplacementException e)when(e.Code=="ExpiredOrDrained"){drained=true;}
 Check("retired client lease refused after drain",drained);
 Check("fresh mTLS continues after failed replacement",await Call(b.Runtime,"text-api",a.Port,"identity")==200);
}
catch(Exception error) {
 Console.Error.WriteLine(JsonSerializer.Serialize(new { Status="FAILED",ExceptionType=error.GetType().Name,ChecksCompleted=checks.Count,Cases=checks,Failed=failures,Observations=observations }));throw;
}
finally {
 foreach(var app in apps.AsEnumerable().Reverse()) {using var stop=new CancellationTokenSource(TimeSpan.FromSeconds(10));await app.StopAsync(stop.Token);await app.DisposeAsync();}
 foreach(var certificate in material)certificate.Dispose();
 Console.Error.WriteLine(JsonSerializer.Serialize(new { Cleanup="NORMAL_SHUTDOWN",HostsDisposed=apps.Count,RemainingOwnedNativeKeyFiles=TlsCredentialImport.RemainingOwnedNativeKeyFiles }));
}
Check("temporary native TLS key containers removed",TlsCredentialImport.RemainingOwnedNativeKeyFiles==0);
Console.WriteLine(JsonSerializer.Serialize(new { Status=failures.Count==0?"PASS":"FAILED",Checks=checks.Count,Passed=checks.Count-failures.Count,Failed=failures,Cases=checks,Runtime=Environment.Version.ToString(),Services=2,Processes=2,Transport="REAL_LOOPBACK_MTLS",Observations=observations,CloudCalls=0,PrivateMaterial="EPHEMERAL_TEST_ONLY",PersistentCa=false,RemainingOwnedNativeKeyFiles=TlsCredentialImport.RemainingOwnedNativeKeyFiles,ProductionQualified=false }));

Environment.ExitCode=failures.Count==0?0:1;

// A fresh process never receives or creates a client key/certificate, and never calls LocalCertificateAuthority.
static async Task AnonymousNoKey() {
    using var input=JsonDocument.Parse(await Console.In.ReadLineAsync()??throw new InvalidOperationException("PUBLIC_BOOTSTRAP_REQUIRED"));
    var port=input.RootElement.GetProperty("Port").GetInt32();var root=new CertificateData(input.RootElement.GetProperty("Root").GetBytesFromBase64());
    if(port is <1 or >65535)throw new ArgumentException("LOOPBACK_PORT_REQUIRED");
    var clock=new ServiceIdentity.Pki.Core.SystemClock();
    using var trust=new PeerTrust(new X509CertificateValidator(clock),TrustPolicy.ForLocalDevelopment(root),[EcsDevelopmentIdentity.Profile("text-api",CertificatePurpose.Server)]);
    using var timeout=new CancellationTokenSource(TimeSpan.FromSeconds(8));using var tcp=new TcpClient();
    await tcp.ConnectAsync(IPAddress.Loopback,port,timeout.Token);
    var serverTrusted=false;
    await using var tls=new SslStream(tcp.GetStream(),false,(_,remote,chain,errors)=>serverTrusted=trust.Validate(remote,chain,errors) is not null);
    var rejected=false;var boundary="NOT_REJECTED";int? status=null;
    try {
      await tls.AuthenticateAsClientAsync(new SslClientAuthenticationOptions { TargetHost="localhost",EnabledSslProtocols=SslProtocols.Tls12|SslProtocols.Tls13,AllowTlsResume=false,CertificateChainPolicy=trust.CreateChainPolicy(CertificatePurpose.Server),ClientCertificates=new X509CertificateCollection(),LocalCertificateSelectionCallback=(_,_,_,_,_)=>null! },timeout.Token);
      await tls.WriteAsync(Encoding.ASCII.GetBytes("GET /identity HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"),timeout.Token);
      using var reader=new StreamReader(tls);var response=await reader.ReadToEndAsync(timeout.Token);
      if(response.StartsWith("HTTP/1.1 ")) { status=int.Parse(response.Split(' ')[1]);rejected=status is 401 or 403;boundary="HTTP_"+status; }
      else {rejected=true;boundary="TLS_CLOSED_NO_HTTP";}
    } catch(Exception e)when(e is AuthenticationException or IOException) { rejected=true;boundary="TLS_OR_IO"; }
    rejected &= serverTrusted;
    Console.WriteLine(JsonSerializer.Serialize(new { Rejected=rejected,ServerTrusted=serverTrusted,Boundary=boundary,HttpStatus=status,ProcessId=Environment.ProcessId,ClientLocalPort=((IPEndPoint)tcp.Client.LocalEndPoint!).Port,PrivateMaterialProvided=false,PrivateMaterialCreated=false,PresentedClientFingerprint=tls.LocalCertificate is null?null:Convert.ToHexString(SHA256.HashData(tls.LocalCertificate.GetRawCertData())).ToLowerInvariant() }));
    Environment.ExitCode=rejected?0:1;
}
