variable "sg_id" {
  type        = string
  description = "Security Group ID applied to NAT instances."
}

variable "route_table_a_id" {
  type        = string
  description = "ID of the private route table for Availability Zone A."
}

variable "route_table_b_id" {
  type        = string
  description = "ID of the private route table for Availability Zone B."
}

variable "subnet_a_id" {
  type        = string
  description = "ID of the public subnet in Availability Zone A."
}

variable "subnet_b_id" {
  type        = string
  description = "ID of the public subnet in Availability Zone B."
}

variable "name" {
  type        = string
  description = "Name prefix used for all NAT-related resources."
}

variable "tags" {
  type        = map(string)
  description = "Common set of resource tags applied across the module."
}

variable "azs" {
  type        = list(string)
  description = "Optional override for Availability Zones (e.g. [\"us-east-1a\", \"us-east-1b\"])."
}

variable "enable_alarms" {
  type        = bool
  description = "Enable CloudWatch alarms for NAT ASGs"
  default     = true
}

variable "alerts_topic_arn" {
  type        = string
  description = "SNS topic ARN for alarm notifications"
}
