module "vpc" {
  source              = "./modules/vpc"
  protected_flow_role = local.expected["prod/flow"]
  name                = local.name
  tags                = local.tags
  azs                 = local.azs
}
module "alb" {
  source           = "./modules/alb"
  name             = local.name
  tags             = local.tags
  vpc_id           = module.vpc.vpc_id
  sg_id            = aws_security_group.alb_demo.id
  subnet_ids       = module.vpc.private_subnet_ids
  alerts_topic_arn = var.alerts_topic_arn
}
