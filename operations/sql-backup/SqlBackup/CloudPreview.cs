using System.Text.Json.Nodes;

namespace SqlBackup;

public static class CloudPreview
{
    public static object Render(Options o)
    {
        o.Validate();
        var bucket = "arn:aws:s3:::" + o.Bucket; var objects = bucket + "/" + o.Prefix + "/*";
        object Policy(params object[] statements) => new { Version = "2012-10-17", Statement = statements };
        object KmsStatement() => new { Effect = "Allow", Action = new[] {"kms:GenerateDataKey", "kms:Decrypt"}, Resource = o.BackupKeyArn,
            Condition = new Dictionary<string, object> { ["StringEquals"] = new Dictionary<string, string> { ["kms:ViaService"] = "s3.us-east-1.amazonaws.com" },
                ["ArnLike"] = new Dictionary<string, string> { ["kms:EncryptionContext:aws:s3:arn"] = objects } } };
        return new
        {
            Status = "PROPOSED_NOT_INSTALLED", Account = "341936017254", Region = "us-east-1",
            Bucket = new { Name = o.Bucket, DedicatedRetainedOutsideDevDown = true, BlockPublicAccess = true, Versioning = "Enabled", Encryption = new { Algorithm = "aws:kms", KeyArn = o.BackupKeyArn, BucketKeyEnabled = false },
                Lifecycle = new { Status = "PROPOSED", Prefix = o.Prefix + "/", ExpirationDays = o.ProposedRetentionDays, NoncurrentVersionExpirationDays = o.ProposedRetentionDays, AbortIncompleteMultipartUploadDays = 1 } },
            ProducerPolicy = Policy(new { Effect = "Allow", Action = new[] {"s3:PutObject", "s3:GetObject", "s3:GetObjectVersion"}, Resource = objects }, KmsStatement()),
            ObserverRestorePolicy = Policy(new { Effect = "Allow", Action = new[] {"s3:GetObject", "s3:GetObjectVersion"}, Resource = objects },
                new { Effect = "Allow", Action = "s3:ListBucket", Resource = bucket, Condition = new Dictionary<string, object> { ["StringLike"] = new Dictionary<string, string> { ["s3:prefix"] = o.Prefix + "/runs/*" } } },
                new { Effect = "Allow", Action = "kms:Decrypt", Resource = o.BackupKeyArn, Condition = new Dictionary<string, object> { ["StringEquals"] = new Dictionary<string, string> { ["kms:ViaService"] = "s3.us-east-1.amazonaws.com" }, ["ArnLike"] = new Dictionary<string, string> { ["kms:EncryptionContext:aws:s3:arn"] = objects } } }),
            BucketPolicy = Policy(new { Sid = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*", Resource = new[] {bucket, bucket + "/*"}, Condition = new Dictionary<string, object> { ["Bool"] = new Dictionary<string, string> { ["aws:SecureTransport"] = "false" } } },
                new { Sid = "DenyWrongEncryption", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = objects, Condition = new Dictionary<string, object> { ["StringNotEquals"] = new Dictionary<string, string> { ["s3:x-amz-server-side-encryption"] = "aws:kms" } } },
                new { Sid = "DenyWrongKey", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = objects, Condition = new Dictionary<string, object> { ["StringNotEquals"] = new Dictionary<string, string> { ["s3:x-amz-server-side-encryption-aws-kms-key-id"] = o.BackupKeyArn } } },
                new { Sid = "DenyNonConditionalCreation", Effect = "Deny", Principal = "*", Action = "s3:PutObject", Resource = objects, Condition = new Dictionary<string, object> { ["StringNotEquals"] = new Dictionary<string, string> { ["s3:if-none-match"] = "*" } } }),
            OriginalTextKeyMustBeRetained = o.TextKeyArn,
            SqlBackupPermission = $"USE {Names.Quote(o.Database)}; ALTER ROLE db_backupoperator ADD MEMBER [dedicated_backup_user];",
            VerifierRestorePermission = "Separate restricted administrative SQL connection: CREATE DATABASE is required by RESTORE metadata/VERIFYONLY. Never grant it to the application or backup-only login.",
            Network = "PROPOSED S3 gateway endpoint on both private route tables; scope bucket/endpoint policies to these roles and bucket. No network change is installed.",
            Monitoring = new { Status = "PROPOSED", o.ProposedIntervalHours, o.ProposedMaxAgeHours, FailedAttempt = "Nonzero process exit + sanitized last-attempt.json; forward service logs in a separately approved installation", MissingAttempt = "Run check --aws --expected-up true from an independent host/scheduler; notify only after configuring an authorized channel", Rpo = "UNDECIDED_UNMEASURED", Rto = "UNDECIDED_UNMEASURED" }
        };
    }
}
