resource "aws_security_group" "alb_demo" {
  name                   = "${local.name}-alb-sg"
  description            = "Security Group for the internal ALB used by the demo service."
  vpc_id                 = module.vpc.vpc_id
  revoke_rules_on_delete = true
  tags                   = merge(local.tags, { Name = "${local.name}-alb-sg" })
}

resource "aws_security_group" "vpc_link" {
  name                   = "${local.name}-vpc-link-sg"
  description            = "Security Group for API Gateway VPC Link ENIs."
  vpc_id                 = module.vpc.vpc_id
  revoke_rules_on_delete = true
  tags                   = merge(local.tags, { Name = "${local.name}-vpc-link-sg" })
}

resource "aws_security_group" "nat_instance" {
  name                   = "${local.name}-nat-instance-sg"
  description            = "Security Group for high-availability NAT instances."
  vpc_id                 = module.vpc.vpc_id
  revoke_rules_on_delete = true
  tags                   = merge(local.tags, { Name = "${local.name}-nat-instance-sg" })
}

resource "aws_security_group" "fargate_demo" {
  name                   = "${local.name}-fargate-sg"
  description            = "Security Group for the Fargate demo service."
  vpc_id                 = module.vpc.vpc_id
  revoke_rules_on_delete = true
  tags                   = merge(local.tags, { Name = "${local.name}-fargate-sg" })
}

resource "aws_security_group" "db_instance" {
  name                   = "${local.name}-db-instance-sg"
  description            = "Security Group for the demo database instance."
  vpc_id                 = module.vpc.vpc_id
  revoke_rules_on_delete = true
  tags                   = merge(local.tags, { Name = "${local.name}-db-instance-sg" })
}
