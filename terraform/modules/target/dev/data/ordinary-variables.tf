variable "instance_type" {
  description = "EC2 instance type for the SQL server."
  type        = string
  default     = "t3a.small"
}
variable "cpu_credits" {
  description = "CPU credit mode for T family instances: standard | unlimited."
  type        = string
  default     = "standard"
  validation {
    condition     = contains(["standard", "unlimited"], var.cpu_credits)
    error_message = "cpu_credits must be 'standard' or 'unlimited'."
  }
}
variable "volume_size_gb" {
  description = "Root volume size in GiB."
  type        = number
  default     = 30
}
variable "key_name" {
  description = "Optional EC2 KeyPair for emergency SSH access."
  type        = string
  default     = null
}
variable "app_db" {
  description = "Name of the application's database."
  type        = string
  default     = "demodb"
}
variable "app_user" {
  description = "SQL user for the application."
  type        = string
  default     = "fargate_user"
}
variable "enable_alarms" {
  description = "Whether to create basic CloudWatch alarms for the EC2 instance."
  type        = bool
  default     = true
}
variable "private_subnet_ids" {
  description = "List of private subnet IDs where the EC2 instance will run."
  type        = list(string)
}
variable "db_instance_sg_id" {
  description = "Security Group ID applied to the SQL Server EC2 instance."
  type        = string
}
variable "alerts_topic_arn" {
  type        = string
  description = "SNS topic ARN for alarm notifications"
}

variable "recovery_target_subnet_id" {
  description = "Explicit reviewed recovery target; null preserves original placement. Membership is not native VPC/AZ proof."
  type        = string
  default     = null
  nullable    = true
  validation {
    condition     = var.recovery_target_subnet_id == null ? true : can(regex("^subnet-[0-9a-f]{8,17}$", var.recovery_target_subnet_id)) && contains(var.private_subnet_ids, var.recovery_target_subnet_id)
    error_message = "Recovery target must be one of the reviewed private subnets."
  }
}

variable "protected_sql_ami" { type = string }

# Proposed explicit install only. Protected source/runtime admission must be renewed
# before use; ordinary callers have no new installed authority from this declaration.
variable "sql_backup_cohost" {
  default = null
  type = object({
    artifact                           = object({ Bucket = string, Key = string, VersionId = string, Sha256 = string, BucketKeyEnabled = bool })
    backup                             = object({ Database = string, StagingDirectory = string, RestoreDirectory = string, Bucket = string, Prefix = string, BackupKeyArn = string, TextKeyArn = string, ExpectedEc2RoleName = string, MaxBackupBytes = number, FreeReserveBytes = number, TimeoutSeconds = number, ProposedIntervalHours = number, ProposedRetentionDays = number, ProposedMaxAgeHours = number, RetainLocalVerifiedBackups = number })
    sentinel                           = object({ SchemaVersion = number, Placement = string, Account = string, Region = string, RunId = string, Subject = string, StartsAt = string, ExpiresAt = string, CadenceSeconds = number, ReminderSeconds = number, PublishAttempts = number, WatchdogSeconds = number, ExpectedUp = bool, Portable = optional(object({ SchemaVersion = number, ContractSha256 = string })) })
    enable_after_native_gates          = optional(bool, false)
    enable_producer_after_native_gates = optional(bool, false)
  })
  validation {
    condition = var.sql_backup_cohost == null ? true : (
      length(base64encode(jsonencode(var.sql_backup_cohost))) <= 4096 &&
      (!var.sql_backup_cohost.enable_producer_after_native_gates || var.sql_backup_cohost.enable_after_native_gates) &&
      var.sql_backup_cohost.sentinel.Account == var.account_id && var.sql_backup_cohost.sentinel.Region == var.region &&
      var.sql_backup_cohost.sentinel.Placement == "SQL_HOST" &&
      var.sql_backup_cohost.backup.ExpectedEc2RoleName == "demo-dev-data-sql-ec2-role" &&
      var.sql_backup_cohost.artifact.Bucket == var.sql_backup_cohost.backup.Bucket &&
      !var.sql_backup_cohost.artifact.BucketKeyEnabled &&
      can(regex("^[a-f0-9]{64}$", var.sql_backup_cohost.artifact.Sha256)) &&
      var.sql_backup_cohost.artifact.VersionId != "null" && length(var.sql_backup_cohost.artifact.VersionId) > 0 &&
      var.sql_backup_cohost.artifact.Key == "terragrunt-demo/dev/sql-backup-artifacts/${var.sql_backup_cohost.sentinel.RunId}/${var.sql_backup_cohost.artifact.Sha256}/SqlBackup.tar"
    )
    error_message = "Exact SQL-host/account/region and immutable, non-bucket-key package required. Native admission remains separate."
  }
}
