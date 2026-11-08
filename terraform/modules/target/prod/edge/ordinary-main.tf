module "apigateway" {
  source = "./modules/apigateway"

  name = local.name
  tags = local.tags

  vpc_link_id          = module.vpclink.vpc_link_id
  alb_listener_arn     = var.alb_listener_arn
  cors_allowed_origins = var.cors_allowed_origins
}

module "vpclink" {
  source = "./modules/vpc_link"

  name = local.name
  tags = local.tags

  security_group_ids = [var.vpc_link_sg_id]
  private_subnet_ids = var.private_subnet_ids
}
