output "private_subnet_ids" {
  value       = module.vpc.private_subnet_ids
  description = "List of private subnet IDs created by the VPC module."
}

output "alb_listener_arn" {
  value       = module.alb.alb_listener_arn
  description = "ARN of the ALB listener used for API Gateway integrations."
}

output "alb_candidate_rule_arn" {
  value       = module.alb.alb_candidate_rule_arn
  description = "ARN of the ALB listener rule used as candidate in blue/green deploys."
}

# Backward compatible alias with legacy typo.
output "alb_cantidate_rule_arn" {
  value       = module.alb.alb_candidate_rule_arn
  description = "DEPRECATED: use alb_candidate_rule_arn."
}

output "demo_blue_tg_arn" {
  value       = module.alb.demo_blue_tg_arn
  description = "ARN of the target group associated with the demo service."
}

output "demo_green_tg_arn" {
  value       = module.alb.demo_green_tg_arn
  description = "ARN of the target group associated with the demo service."
}




output "vpc_id" {
  value       = module.vpc.vpc_id
  description = "ID of the VPC deployed by this environment."
}

output "vpc_link_sg_id" {
  value       = aws_security_group.vpc_link.id
  description = "Security Group ID used by the API Gateway VPC Link connection."
}

output "demo_sg_id" {
  value       = aws_security_group.fargate_demo.id
  description = "Security Group ID assigned to the Fargate demo service."
}

output "db_instance_sg_id" {
  value       = aws_security_group.db_instance.id
  description = "Security Group ID assigned to the demo database instance."
}
