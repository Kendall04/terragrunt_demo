using System.Security.Cryptography;
using Amazon.DynamoDBv2;
using Amazon.DynamoDBv2.Model;
using Amazon.S3;
using Amazon.S3.Model;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Operations;
using Sentinel.Persistence.DynamoDb;
using Sentinel.Persistence.S3;

namespace Ecs.Backup.Portable.Host;

// An append-only disposition of four authenticated archive failures. No original
// effect, attempt, audit or operational checkpoint is updated; SNS is never used.
public sealed record ArchiveFailurePin(string EffectId, string EffectSha256, string AuditId, string AuditSha256);
public sealed record ArchiveCompensationReceipt(int SchemaVersion, string Namespace, ArchiveFailurePin Original,
    string Key, string Sha256, string VersionId, string KmsKey, DateTimeOffset VerifiedAt);
public sealed class ArchiveCompensation(IAmazonDynamoDB ddb, IAmazonS3 s3, DynamoOptions options, ArchiveOptions archiveOptions) {
    public static readonly ArchiveFailurePin[] Pins = [
        new("cdd9e53970f5082d9445890c20cadd23f70566386f4d8c06197d3dcc01296ae5", "b513af7039906a29219a304d676f48424eac96ee290a4f9091453414c032764e", "3c991c8985e363f41936c589624eb95f206756db71e35db608f504a78aa66ae3", "89baad125248f457b9cc033711848653516b428b40ba6d38a8a72d5c216cbe8f"),
        new("fd16c3dc509fae493a7fa6df49b66b60b398650dce48d187f63f0de83b9791c2", "701ae14dd9ab5d07d5984a7c867c80875a9548602f86626f22614919179ae0bf", "4f4156fc706b95f208f046dc3290a5bbe18a3fc072148ca3804138a932ff3ddc", "ee0e78930de02b8182c5f178eb23ecdc6de3da2e6bd2e0f8a1792e80c5f36cec"),
        new("ec197e9019e2406d0b625063e0231d99fff1310a2285a06a049ccb1e80aaa803", "a82921b1795cc9ddb6bbf72c6adf287f249b16850f259508adf906344a77718e", "62fde6508fd63d36a0ea5306079ba3ef2a363771037664521e58424dc9563c92", "625a5ba50884601a81742535333de86d182f1b86e9ac386555c13256b699f167"),
        new("35d0cdbdd9cdfae95bd8313f799cd0f2c1ec48aace1f9610d1d2f036a84c87fd", "e97a60ef927c5afb42dd9072e4036059e0168735b995b7ac0d7451562474c2b6", "2e4a54890df920678716a4425a41156cd2d0232f84e08c69c91b8efe8c63f9d0", "f927748b21124089b97219854e1dd9572f8001bdec75b191d0caa4548e2e4f8c")
    ];
    private readonly PhysicalLayout layout = new(options);
    private readonly S3ArchiveAdapter archive = new(s3, archiveOptions);
    public int Requests { get; private set; }
    static string Sha(byte[] raw) => Convert.ToHexStringLower(SHA256.HashData(raw));
    void Count() { if (++Requests > 64) throw new InvalidOperationException("Compensation request budget exhausted."); }
    Dictionary<string, AttributeValue>? Read(string sk) {
        Count(); var r = ddb.GetItemAsync(new GetItemRequest { TableName=options.Table, Key=layout.Key(sk), ConsistentRead=true }).GetAwaiter().GetResult();
        return r.Item is { Count: >0 } ? r.Item : null;
    }
    (OutboxEntry Effect, AuditRecord Audit) Originals(ArchiveFailurePin pin) {
        var effect=Read(PhysicalLayout.Effect(pin.EffectId)); var audit=Read(PhysicalLayout.Audit(pin.AuditId));
        if (effect is null || audit is null || Sha(effect["Data"].B.ToArray())!=pin.EffectSha256 || Sha(audit["Data"].B.ToArray())!=pin.AuditSha256)
            throw new InvalidDataException("Original archive evidence differs; preserve and investigate.");
        var e=PhysicalLayout.Payload<OutboxEntry>(effect); var a=PhysicalLayout.Payload<AuditRecord>(audit);
        if(e.Id!=pin.EffectId || a.Id!=pin.AuditId || e.AuditId!=a.Id || e.AggregateKey!=a.AggregateKey || e.Kind!=WorkKind.ArchiveDecision || e.Status!=OutboxStatus.PermanentFailure || e.Intent is not null)
            throw new InvalidDataException("Only the exact permanent archive failures may be compensated.");
        return (e,a);
    }
    static string ReceiptKey(ArchiveFailurePin pin) => "AC#"+pin.EffectId;
    public static bool ValidReceipt(ArchiveCompensationReceipt r, ArchiveFailurePin pin, string ns, string key, string digest, string kms, DateTimeOffset now) =>
        r.SchemaVersion==1 && r.Namespace==ns && r.Original==pin && r.Key==key && r.Sha256==digest &&
        !string.IsNullOrWhiteSpace(r.VersionId) && r.VersionId!="null" && r.KmsKey==kms &&
        r.VerifiedAt.Offset==TimeSpan.Zero && r.VerifiedAt>=DateTimeOffset.Parse("2026-11-06T04:55:45Z") && r.VerifiedAt<=now;
    public int VerifiedCount(DateTimeOffset now) {
        int count=0;
        foreach(var pin in Pins) {
            var (_,a)=Originals(pin); var item=Read(ReceiptKey(pin));
            if(item is null)continue;
            var r=PhysicalLayout.Payload<ArchiveCompensationReceipt>(item);
            if(!ValidReceipt(r,pin,options.Namespace,archive.Key(a),Sha(archive.Bytes(a)),archiveOptions.KmsKeyId!,now))
                throw new InvalidDataException("Archive compensation receipt is not verified.");
            count++;
        }
        return count;
    }
    public static GetObjectResponse CreateOnlyAndRead(IAmazonS3 client,string bucket,string key,byte[] bytes,string kms,Action count) {
        // A missing-key GET is 403 without ListBucket. Do not reinterpret that
        // denial as absence or expand IAM: conditional PUT is the atomic guard.
        count(); using var input=new MemoryStream(bytes);
        try {
            client.PutObjectAsync(new PutObjectRequest{BucketName=bucket,Key=key,InputStream=input,
                IfNoneMatch="*",ChecksumSHA256=Convert.ToBase64String(SHA256.HashData(bytes)),ContentType="application/json",
                ServerSideEncryptionMethod=ServerSideEncryptionMethod.AWSKMS,ServerSideEncryptionKeyManagementServiceKeyId=kms}).GetAwaiter().GetResult();
        }
        catch(AmazonS3Exception e) when(e.StatusCode==System.Net.HttpStatusCode.PreconditionFailed) {
            // Existing bytes must still pass the caller's full verification.
        }
        // Every other failure, including an ambiguous write, stops without retry.
        count();return client.GetObjectAsync(new GetObjectRequest{BucketName=bucket,Key=key}).GetAwaiter().GetResult();
    }
    public IReadOnlyList<ArchiveCompensationReceipt> Execute(DateTimeOffset now) {
        if(options.Namespace!="NS#b752b39384784041f4d8fe445ceb7002180c236cfa595219f87701424ae032b2" || now>=DateTimeOffset.Parse("2026-11-09T04:00:00Z"))
            throw new InvalidOperationException("Outside approved compensation scope/window.");
        List<ArchiveCompensationReceipt> receipts=[];
        foreach(var pin in Pins) {
            var (_,a)=Originals(pin); var key=archive.Key(a); var bytes=archive.Bytes(a); var digest=Sha(bytes);
            var previous=Read(ReceiptKey(pin));
            if(previous is not null) {
                var r=PhysicalLayout.Payload<ArchiveCompensationReceipt>(previous);
                if(!ValidReceipt(r,pin,options.Namespace,key,digest,archiveOptions.KmsKeyId!,now))throw new InvalidDataException("Existing receipt mismatch.");
                receipts.Add(r); continue;
            }
            var found=CreateOnlyAndRead(s3,archiveOptions.Bucket,key,bytes,archiveOptions.KmsKeyId!,Count);
            using(found) {
                using var output=new MemoryStream(); byte[] buffer=new byte[8192]; int n;
                while((n=found.ResponseStream.Read(buffer))>0) { if(output.Length+n>bytes.Length)throw new InvalidDataException("Archive size mismatch."); output.Write(buffer,0,n); }
                if(!output.ToArray().AsSpan().SequenceEqual(bytes) || found.ServerSideEncryptionMethod!=ServerSideEncryptionMethod.AWSKMS || found.ServerSideEncryptionKeyManagementServiceKeyId!=archiveOptions.KmsKeyId || string.IsNullOrEmpty(found.VersionId) || found.VersionId=="null")
                    throw new InvalidDataException("Archive bytes, encryption or version unconfirmed.");
                var receipt=new ArchiveCompensationReceipt(1,options.Namespace,pin,key,digest,found.VersionId,archiveOptions.KmsKeyId!,now);
                Count(); ddb.PutItemAsync(new PutItemRequest{TableName=options.Table,Item=layout.Item(ReceiptKey(pin),receipt),ConditionExpression="attribute_not_exists(PK)"}).GetAwaiter().GetResult();
                var verified=Read(ReceiptKey(pin));
                if(verified is null || PhysicalLayout.Payload<ArchiveCompensationReceipt>(verified)!=receipt)throw new IOException("Receipt write unconfirmed; do not retry.");
                receipts.Add(receipt);
            }
        }
        return receipts;
    }
    public static OperationalRecord? CurrentHealthView(OperationalRecord? raw,int verified) {
        if(verified<0 || verified>4 || raw is not null && raw.UnresolvedFailures<verified)throw new InvalidDataException("Failure accounting inconsistent.");
        return raw is null ? null : raw with {UnresolvedFailures=raw.UnresolvedFailures-verified};
    }
}
