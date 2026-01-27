variable "env" { type = string }

variable "project" { type = string }

variable "create_github_oidc_provider" {
  type    = bool
  default = true
}

variable "github_owner" {
  type = string
}

variable "github_repo" {
  type = string
}

variable "alert_email" {
  type        = string
  description = "Email to receive CloudWatch alarms"
}
