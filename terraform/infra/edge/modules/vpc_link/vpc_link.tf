resource "aws_apigatewayv2_vpc_link" "this" {
  # Name visible in AWS console / API Gateway configuration
  name = "${var.name}-vpc-link"

  # ENIs created by the VPC Link will use these SGs
  security_group_ids = var.security_group_ids

  # The ENIs will be placed inside these private subnets
  subnet_ids = var.private_subnet_ids

  # Standard tagging
  tags = merge(var.tags, { Name = "${var.name}-vpc-link" })
}
