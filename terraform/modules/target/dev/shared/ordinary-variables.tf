variable "alert_email" {
  type        = string
  sensitive   = true
  default     = null
  description = "Optional confirmed recipient; null leaves email notifications inactive"
}

variable "alerts_topic_policy_base" {
  type        = string
  nullable    = false
  description = "Exact original SNS policy read and reviewed privately; preserve all permissions and Deny statements."
  validation {
    condition = can(jsondecode(var.alerts_topic_policy_base).Statement) && try(
      contains(["2008-10-17", "2012-10-17"], jsondecode(var.alerts_topic_policy_base).Version) &&
      length(jsondecode(var.alerts_topic_policy_base).Statement) > 0, false
    )
    error_message = "An explicit valid original SNS policy is required; no empty or permissive default."
  }
}
