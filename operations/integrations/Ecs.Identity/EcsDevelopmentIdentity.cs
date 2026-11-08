using System.Security.Cryptography.X509Certificates;
using Microsoft.Extensions.DependencyInjection;
using ServiceIdentity.Pki.Core;
using ServiceIdentity.Pki.Integration.AspNetCore;

namespace Ecs.Identity;

/// <summary>Explicit local-development consumer binding. No issuer, enrollment, persistent CA or AWS configuration.</summary>
public static class EcsDevelopmentIdentity {
    public const string Read="ecs-local.identity.read";
    public const string Observe="ecs-local.backup.observe";
    public static ServiceId Id(string service)=>service is "text-api" or "recovery-observer"
        ?new("ecs-demo.example","local-development",service):throw new ArgumentException("Unknown local consumer identity.");
    public static CertificateProfile Profile(string service,CertificatePurpose purpose)=>new(Id(service),purpose,purpose==CertificatePurpose.Server?"localhost":null);
    public static IServiceCollection AddEcsDevelopmentIdentity(this IServiceCollection services,string service,
        CertificateData root,CertificateData intermediate,X509Certificate2 server,X509Certificate2 client) {
        // Caller owns issuance, trust selection and material; the framework owns imported generation snapshots.
        return services.AddServiceIdentityPki(o=>{
            o.Trust=TrustPolicy.ForLocalDevelopment(root);o.Server=Profile(service,CertificatePurpose.Server);o.Client=Profile(service,CertificatePurpose.Client);
            o.IncomingClients.AddRange([Profile("text-api",CertificatePurpose.Client),Profile("recovery-observer",CertificatePurpose.Client)]);
            o.Operations.Add(Read,[Id("text-api"),Id("recovery-observer")]);
            o.Operations.Add(Observe,[Id("recovery-observer")]);
            o.Drain=TimeSpan.FromMilliseconds(500);
        },(_,manager)=>{using var prepared=manager.Prepare("initial",server,client,intermediate);manager.Activate(prepared,0);});
    }
}
