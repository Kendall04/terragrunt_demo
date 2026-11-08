using Ecs.Backup.Portable.Host;
using Sentinel.Core;
using Sentinel.Operations;
using Sentinel.Portable;
using Amazon.S3;
using Amazon.S3.Model;
using Amazon.Runtime;
internal static class ArchiveCompensationChecks {
 sealed class Store(System.Net.HttpStatusCode status) : AmazonS3Client(new BasicAWSCredentials("fixture","fixture"),new AmazonS3Config{RegionEndpoint=Amazon.RegionEndpoint.USEast1}) {
  public int Writes,Reads;public bool Conditional;
  public override Task<PutObjectResponse> PutObjectAsync(PutObjectRequest request,CancellationToken cancellationToken=default) {
   Writes++;Conditional=request.IfNoneMatch=="*" && request.ServerSideEncryptionMethod==ServerSideEncryptionMethod.AWSKMS && request.ServerSideEncryptionKeyManagementServiceKeyId=="kms" && request.ChecksumSHA256 is not null;
   if(status!=System.Net.HttpStatusCode.OK)throw new AmazonS3Exception("bounded fixture"){StatusCode=status};
   return Task.FromResult(new PutObjectResponse());
  }
  public override Task<GetObjectResponse> GetObjectAsync(GetObjectRequest request,CancellationToken cancellationToken=default) {
   if(Writes!=1)throw new Exception("Read before conditional create");Reads++;
   return Task.FromResult(new GetObjectResponse{ResponseStream=new MemoryStream([1,2,3]),VersionId="real-version"});
  }
 }
 public static void Run(Installation c,Action<string,bool> check) {
  foreach(var status in new[]{System.Net.HttpStatusCode.OK,System.Net.HttpStatusCode.PreconditionFailed,System.Net.HttpStatusCode.Forbidden,System.Net.HttpStatusCode.InternalServerError}) {
   using var store=new Store(status);int calls=0;
   try {using var response=ArchiveCompensation.CreateOnlyAndRead(store,"bucket","key",[1,2,3],"kms",()=>calls++);check("create-only result read back",status is System.Net.HttpStatusCode.OK or System.Net.HttpStatusCode.PreconditionFailed && calls==2);}
   catch(AmazonS3Exception) {check("denied or ambiguous write stops",status is System.Net.HttpStatusCode.Forbidden or System.Net.HttpStatusCode.InternalServerError && calls==1);}
   check("no overwrite or automatic retry",store.Writes==1 && store.Conditional && store.Reads==(calls==2?1:0));
  }
  var now=DateTimeOffset.Parse("2026-11-06T06:00:00Z");var pin=ArchiveCompensation.Pins[0];
  var receipt=new ArchiveCompensationReceipt(1,"namespace",pin,"archive-key",new string('a',64),"actual-version","key",now);
  bool Valid(ArchiveCompensationReceipt r)=>ArchiveCompensation.ValidReceipt(r,pin,"namespace","archive-key",new string('a',64),"key",now);
  check("exact append-only compensation admitted",Valid(receipt));
  foreach(var changed in new[]{receipt with{Original=pin with{EffectSha256=new string('0',64)}},receipt with{Namespace="other"},receipt with{Key="other"},receipt with{Sha256=new string('0',64)},receipt with{VersionId="null"},receipt with{KmsKey="other"},receipt with{VerifiedAt=now.AddSeconds(1)}})
   check("changed compensation refused",!Valid(changed));
  var scope=new OperationalScope(c.Project,c.Environment,c.Consumer,"worker","portable");
  var raw=OperationalRecord.Empty(scope,c.Operations,now) with{UnresolvedFailures=5};var original=DomainJson.Serialize(raw);
  check("new fifth failure not masked",ArchiveCompensation.CurrentHealthView(raw,4)!.UnresolvedFailures==1);
  check("no receipt means no suppression",ArchiveCompensation.CurrentHealthView(raw,0)!.UnresolvedFailures==5);
  check("raw journal unchanged",DomainJson.Serialize(raw)==original);
  try {ArchiveCompensation.CurrentHealthView(raw with{UnresolvedFailures=3},4);throw new Exception("Not rejected");}catch(InvalidDataException){check("inconsistent accounting rejected",true);}
  var nat=new MonitorDefinition("nat-a-egress","report","nat/dev/a","lt4-e13v6","Kendall",MonitorModel.Condition,Assurance.Reported,["nat-observer"],TimeSpan.FromMinutes(2),TimeSpan.FromMinutes(3),TimeSpan.FromMinutes(3),TimeSpan.FromMinutes(1));
  var extended=c with{Monitors=c.Monitors.Add(nat)};extended.Validate();
  foreach(var m in c.Monitors) check("historical SQL catalog unchanged "+m.Id,DomainJson.Serialize(c.Catalog())==DomainJson.Serialize(extended.CatalogFor(m.Key)));
  check("new NAT catalog has own content identity",extended.CatalogFor(nat.Key).Version!=c.Catalog().Version && extended.CatalogFor(nat.Key).Services.Length==1);
  check("operational namespace profile unchanged",DomainJson.Serialize(extended.Operations)==DomainJson.Serialize(c.Operations));
 }
}
