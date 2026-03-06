# ─────────────────────────────────────────────────────────────
# Security Group for the internal ALB used by the demo service.
# Allows traffic from the API Gateway VPC Link.
# ─────────────────────────────────────────────────────────────
resource "aws_security_group" "alb_demo" {
  name                   = "${local.name}-alb-sg"
  description            = "Security Group for the internal ALB used by the demo service."
  vpc_id                 = module.vpc.vpc_id
  revoke_rules_on_delete = true
  tags                   = merge(local.tags, { Name = "${local.name}-alb-sg" })
}

# ─────────────────────────────────────────────────────────────
# Security Group for the API Gateway VPC Link ENIs. 
# Controls traffic entering the VPC through the VPC Link connection. 
# ─────────────────────────────────────────────────────────────
resource "aws_security_group" "vpc_link" {
  name                   = "${local.name}-vpc-link-sg"
  description            = "Security Group for API Gateway VPC Link ENIs."
  vpc_id                 = module.vpc.vpc_id
  revoke_rules_on_delete = true
  tags                   = merge(local.tags, { Name = "${local.name}-vpc-link-sg" })
}

# ─────────────────────────────────────────────────────────────
# Security Group for NAT Instances (High Availability).
# Controls outbound routing and inbound health/maintenance traffic.
# ─────────────────────────────────────────────────────────────
resource "aws_security_group" "nat_instance" {
  name                   = "${local.name}-nat-instance-sg"
  description            = "Security Group for high-availability NAT instances."
  vpc_id                 = module.vpc.vpc_id
  revoke_rules_on_delete = true
  tags                   = merge(local.tags, { Name = "${local.name}-nat-instance-sg" })
}

# ─────────────────────────────────────────────────────────────
# Security Group for the Fargate demo service.
# Controls traffic between the Fargate tasks and the database instance. 
# ─────────────────────────────────────────────────────────────
resource "aws_security_group" "fargate_demo" {
  name                   = "${local.name}-fargate-sg"
  description            = "Security Group for the Fargate demo service."
  vpc_id                 = module.vpc.vpc_id
  revoke_rules_on_delete = true
  tags                   = merge(local.tags, { Name = "${local.name}-fargate-sg" })
}

# ─────────────────────────────────────────────────────────────
# Security Group for the database EC2 instance.
# Allows inbound access from the Fargate demo SG (via rules defined externally).
# ─────────────────────────────────────────────────────────────
resource "aws_security_group" "db_instance" {
  name                   = "${local.name}-db-instance-sg"
  description            = "Security Group for the demo database instance."
  vpc_id                 = module.vpc.vpc_id
  revoke_rules_on_delete = true
  tags                   = merge(local.tags, { Name = "${local.name}-db-instance-sg" })
}
