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
  validation {
    condition     = can(regex("^[A-Za-z_][A-Za-z0-9_]{0,63}$", var.app_db))
    error_message = "SQL identifiers must be reviewed simple names, without quoting or interpolation."
  }
}
variable "app_user" {
  description = "SQL user for the application."
  type        = string
  default     = "fargate_user"
  validation {
    condition     = can(regex("^[A-Za-z_][A-Za-z0-9_]{0,63}$", var.app_user))
    error_message = "SQL identifiers must be reviewed simple names, without quoting or interpolation."
  }
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

# Compatibility tombstone: fail closed on historical Sentinel/cohost inputs.
# SQL backups use the independent native installer, not this retired hook.
variable "sql_backup_cohost" {
  description = "Retired Sentinel integration; only null is accepted."
  type        = any
  default     = null
  validation {
    condition     = var.sql_backup_cohost == null
    error_message = "Sentinel cohost is retired. Use the independent native SQL backup installer."
  }
}


# Proposed only: secret metadata/read permission and privilege changes need separate admission.
variable "sql_database_security" {
  default = null
  type    = object({ migration_user = string, migration_secret_arn = string })
  validation {
    condition = var.sql_database_security == null ? true : (
      can(regex("^[A-Za-z_][A-Za-z0-9_]{0,63}$", var.sql_database_security.migration_user)) &&
      lower(var.sql_database_security.migration_user) != lower(var.app_user) &&
      lower(var.sql_database_security.migration_user) != "sa" && lower(var.app_user) != "sa" &&
      !contains(["master", "model", "msdb", "tempdb"], lower(var.app_db)) &&
      can(regex("^arn:aws:secretsmanager:${var.region}:${var.account_id}:secret:demo/dev/db/sql-migrator-password-[A-Za-z0-9]{6}$", var.sql_database_security.migration_secret_arn))
    )
    error_message = "Exact environment/account migration secret reference and distinct non-SA login required; no new access is installed."
  }
}

variable "recovery_preserve_root_volume" {
  description = "Retain the encrypted source root disk when an explicitly approved cold recovery replaces SQL compute. Retained storage needs separate retirement."
  type        = bool
  default     = false
  nullable    = false
}
