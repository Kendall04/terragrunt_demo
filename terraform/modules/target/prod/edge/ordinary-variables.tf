variable "alb_listener_arn" {
  type = string
}
variable "private_subnet_ids" {
  type = list(string)
}
variable "vpc_link_sg_id" {
  type = string
}
variable "cors_allowed_origins" {
  description = "Allowed browser origins for API Gateway CORS responses."
  type        = list(string)
  default     = []
}
