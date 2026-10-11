variable "vpc_cidr" {
  type        = string
  default     = "10.0.0.0/16"
  description = "CIDR block used to define the main VPC address space."
}

variable "name" {
  type        = string
  description = "Name prefix applied to all VPC-related resources."
}

variable "tags" {
  type        = map(string)
  description = "Common tag map applied across all resources."
}

variable "azs" {
  type        = list(string)
  description = "Optional list of Availability Zones for subnet placement."
}
