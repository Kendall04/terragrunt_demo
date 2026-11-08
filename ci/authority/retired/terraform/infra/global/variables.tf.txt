variable "env" { type = string }

variable "project" { type = string }

variable "alerts_topic_arn" {
  type        = string
  description = "SNS topic ARN for alarm notifications"
}
