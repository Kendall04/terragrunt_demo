# Base service name (used as prefix across resources)
variable "name" {
  description = "Base name for ECS-related resources (prefix)."
  type        = string
}

# ECS cluster where the service will run
variable "cluster_arn" {
  description = "ARN of the ECS cluster."
  type        = string
}

# Networking configuration
variable "subnet_ids" {
  description = "Private subnets assigned to the ECS service."
  type        = list(string)
}

variable "security_group_ids" {
  description = "Security Groups attached to the ENIs of the Fargate tasks."
  type        = list(string)
}

variable "assign_public_ip" {
  description = "Whether Fargate tasks should receive public IPs."
  type        = bool
  default     = false
}

# Service-level configuration
variable "desired_count" {
  description = "Number of service replicas."
  type        = number
  default     = 1
}

variable "task_cpu" {
  description = "Task CPU allocation (e.g. '256', '512')."
  type        = string
  default     = "512"
}

variable "task_memory" {
  description = "Task memory allocation (e.g. '512', '1024')."
  type        = string
  default     = "1024"
}

# ECS task definition identifiers
variable "family" {
  description = "Optional family name for the task definition. Defaults to the service name."
  type        = string
  default     = null
}

variable "container_name" {
  description = "Optional override for the main container name."
  type        = string
  default     = null
}

# Container image
variable "image" {
  description = "Container image (ECR or external registry)."
  type        = string
}

# Ports exposed by the container
variable "port_mappings" {
  description = "List of ports exposed by the main container."
  type = list(object({
    containerPort = number
    protocol      = optional(string, "tcp")
  }))
  default = []
}

# Environment variables (plain text)
variable "environment" {
  description = "Environment variables passed to the container."
  type        = map(string)
  default     = {}
}

# Secrets passed to the container (via task role)
variable "secrets" {
  description = "Map of Secret Manager/SSM parameters injected as container secrets."
  type        = map(string)
  default     = {}
}

# Extra sidecar containers
variable "extra_containers" {
  description = "List of additional container definitions (already jsonencoded)."
  type        = list(any)
  default     = []
}

# Optional container healthcheck
variable "healthcheck" {
  description = "Optional container healthcheck block."
  type = object({
    command     = list(string)
    interval    = optional(number)
    timeout     = optional(number)
    retries     = optional(number)
    startPeriod = optional(number)
  })
  default = null
}

# CloudWatch logging
variable "log_retention_days" {
  description = "CloudWatch LogGroup retention period in days."
  type        = number
  default     = 30
}

# IAM permissions
variable "execution_policy_arns" {
  description = "Additional IAM policies attached to the ExecutionRole."
  type        = list(string)
  default     = []
}

variable "task_policy_arns" {
  description = "Additional IAM policies attached to the TaskRole."
  type        = list(string)
  default     = []
}

# ECS Exec
variable "enable_execute_command" {
  description = "Enable ECS Exec for remote debugging/maintenance."
  type        = bool
  default     = true
}

# Fargate platform version
variable "platform_version" {
  description = "Fargate platform version to use."
  type        = string
  default     = "LATEST"
}

variable "tags" {
  description = "Common resource tags."
  type        = map(string)
  default     = {}
}

# Load balancers (optional)
variable "load_balancers" {
  type = list(object({
    target_group_arn = string
    container_name   = string
    container_port   = number
  }))
  default = []
}

variable "alerts_topic_arn" {
  type        = string
  description = "SNS topic ARN for ECS service alarms"
}

variable "enable_alarms" {
  type        = bool
  description = "Enable ECS CloudWatch alarms"
  default     = true
}
