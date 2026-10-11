output "alb_arn" {
  value       = aws_lb.demo_internal_alb.arn
  description = "ARN of the internal ALB."
}

output "alb_dns_name" {
  value       = aws_lb.demo_internal_alb.dns_name
  description = "DNS name of the internal ALB."
}

output "alb_listener_arn" {
  value       = aws_lb_listener.demo_http_listener.arn
  description = "ARN of the ALB HTTP listener."
}

output "alb_candidate_rule_arn" {
  value       = aws_lb_listener_rule.candidate_rule.arn
  description = "ARN of the ALB listener rule used as candidate in blue/green deploys."
}

# Backward compatible alias with legacy typo.
output "alb_cantidate_rule_arn" {
  value       = aws_lb_listener_rule.candidate_rule.arn
  description = "DEPRECATED: use alb_candidate_rule_arn."
}

output "demo_port" {
  value       = var.demo_port
  description = "Port used by the ALB and ECS service."
}

# Outputs for CI/CD pipelines and ECS service modules
output "demo_blue_tg_arn" {
  description = "ARN of the Blue Target Group (current production TG)"
  value       = aws_lb_target_group.blue.arn
}

output "demo_green_tg_arn" {
  description = "ARN of the Green Target Group (candidate TG for new releases)"
  value       = aws_lb_target_group.green.arn
}
