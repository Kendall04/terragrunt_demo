module "apigateway" {
  source = "./modules/apigateway"

  # Name and tagging for all API Gateway resources
  name = local.name
  tags = local.tags

  # Integration: HTTP API -> VPC Link -> Internal ALB listener
  vpc_link_id      = module.vpclink.vpc_link_id
  alb_listener_arn = var.alb_listener_arn
}

module "vpclink" {
  source = "./modules/vpc_link"

  # Basic naming and tagging
  name = local.name
  tags = local.tags

  # ENIs created by VPC Link must attach to these SGs + private subnets
  security_group_ids = [var.vpc_link_sg_id]
  private_subnet_ids = var.private_subnet_ids
}
