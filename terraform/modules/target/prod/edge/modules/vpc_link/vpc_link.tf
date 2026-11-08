resource "aws_apigatewayv2_vpc_link" "this" {
  name = "${var.name}-vpc-link"

  security_group_ids = var.security_group_ids

  subnet_ids = var.private_subnet_ids

  tags = merge(var.tags, { Name = "${var.name}-vpc-link" })
}
