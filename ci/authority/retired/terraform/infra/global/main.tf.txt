module "vpc" {
  source = "./modules/vpc"
  name   = local.name
  tags   = local.tags
  azs    = local.azs
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

module "nat" {
  source           = "./modules/nat"
  name             = local.name
  tags             = local.tags
  route_table_a_id = module.vpc.private_route_table_ids[0]
  route_table_b_id = module.vpc.private_route_table_ids[1]
  subnet_a_id      = module.vpc.public_subnet_ids[0]
  subnet_b_id      = module.vpc.public_subnet_ids[1]
  sg_id            = aws_security_group.nat_instance.id
  azs              = local.azs
  alerts_topic_arn = var.alerts_topic_arn
  enable_alarms    = true
}
