output "vpc_link_id" {
  description = "ID of the VPC Link created for API Gateway."
  value       = aws_apigatewayv2_vpc_link.this.id
}

output "vpc_link_arn" {
  description = "ARN of the VPC Link for cross-service references or auditing."
  value       = aws_apigatewayv2_vpc_link.this.arn
}
