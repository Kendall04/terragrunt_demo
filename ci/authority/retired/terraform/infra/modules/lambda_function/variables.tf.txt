# Basic name prefix for Lambda and IAM resources
variable "name" { type = string }

# Common resource tags
variable "tags" {
  type    = map(string)
  default = {}
}

variable "role_arn" {
  type        = string
  description = "IAM Role ARN assumed by the Lambda function (must be created outside this module)."
}

# -----------------------------------------------------------------------------
# S3 artifact parameters
# -----------------------------------------------------------------------------

variable "s3_bucket" {
  type        = string
  description = "S3 bucket containing the Lambda deployment package (zip)."
  default     = null
}

variable "s3_key" {
  type        = string
  description = "S3 object key (path) of the Lambda zip file."
  default     = null
}

variable "s3_object_version" {
  type        = string
  description = "S3 object version ID used to enforce idempotent deployments."
  default     = null
}

# -----------------------------------------------------------------------------
# Lambda runtime parameters
# -----------------------------------------------------------------------------

variable "memory_mb" {
  type    = number
  default = 128
}

variable "timeout_sec" {
  type    = number
  default = 10
}

variable "runtime" {
  type    = string
  default = "python3.12"
}

variable "handler" {
  type = string
}

# -----------------------------------------------------------------------------
# Optional VPC configuration
# -----------------------------------------------------------------------------

variable "private_subnet_ids" {
  type        = list(string)
  description = "List of private subnet IDs for the Lambda (if running inside a VPC)."
  default     = null
}

variable "lambda_sg_id" {
  type        = string
  description = "Security Group ID used by the Lambda to access internal resources."
  default     = null
}

# Optional environment variables
variable "environment_variables" {
  type        = map(string)
  description = "Optional map of environment variables for the Lambda function."
  default     = null
}

# Optional local filename for the Lambda zip (mutually exclusive with S3)
variable "filename" {
  type        = string
  description = "Optional local path to the Lambda deployment package (zip). If set, s3_bucket/s3_key/s3_object_version are ignored."
  default     = null
}

variable "invoke_permissions" {
  description = "List of resource-based invoke permissions for the Lambda"
  type = list(object({
    statement_id = string
    principal    = string
    source_arn   = string
  }))
  default = []
}
