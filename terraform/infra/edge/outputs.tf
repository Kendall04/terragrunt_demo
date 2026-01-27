# ==========================================================
# API Gateway outputs
# ==========================================================

output "api_id" {
  description = "ID of the HTTP API Gateway created in the edge layer."
  value       = module.apigateway.api_id
}

output "api_endpoint" {
  description = "Public endpoint URL of the HTTP API Gateway."
  value       = module.apigateway.api_endpoint
}

# ==========================================================
# VPC Link outputs
# ==========================================================

output "vpc_link_id" {
  description = "ID of the VPC Link used for ALB integration."
  value       = module.vpclink.vpc_link_id
}

output "vpc_link_arn" {
  description = "ARN of the VPC Link (useful for audits or cross-service references)."
  value       = module.vpclink.vpc_link_arn
}
