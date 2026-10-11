########
# ALB SG
########

# Ingress: VPC Link -> ALB (Demo service port)
resource "aws_security_group_rule" "alb_ingress_from_vpc_link" {
  type                     = "ingress"
  security_group_id        = aws_security_group.alb_demo.id
  protocol                 = "tcp"
  from_port                = local.port_demo
  to_port                  = local.port_demo
  source_security_group_id = aws_security_group.vpc_link.id
  description              = "VPC Link - ALB (TCP demo port)"
}

# Egress: ALB -> Fargate demo
resource "aws_security_group_rule" "alb_egress_to_fargate_demo" {
  type                     = "egress"
  security_group_id        = aws_security_group.alb_demo.id
  protocol                 = "tcp"
  from_port                = local.port_demo
  to_port                  = local.port_demo
  source_security_group_id = aws_security_group.fargate_demo.id
  description              = "ALB - Fargate demo (TCP demo port)"
}

#############
# VPC Link SG
#############

# Egress: VPC Link -> ALB
resource "aws_security_group_rule" "vpc_link_egress_to_alb" {
  type                     = "egress"
  security_group_id        = aws_security_group.vpc_link.id
  protocol                 = "tcp"
  from_port                = local.port_demo
  to_port                  = local.port_demo
  source_security_group_id = aws_security_group.alb_demo.id
  description              = "VPC Link - ALB (TCP demo port)"
}

#################
# NAT Instance SG
#################

resource "aws_security_group_rule" "nat_ingress_from_vpc" {
  type              = "ingress"
  security_group_id = aws_security_group.nat_instance.id
  protocol          = "-1" # o "tcp" si quieres limitar
  from_port         = 0
  to_port           = 65535
  cidr_blocks       = [module.vpc.vpc_cidr] # ej: "10.0.0.0/16"
  description       = "Allow traffic from private VPC subnets to NAT instance"
}


# Egress: NAT -> Internet

# Reason:
# - NAT instances must allow outbound traffic to 0.0.0.0/0 
# - This is required for routing private subnet outbound traffic to the Internet
#tfsec:ignore:aws-ec2-no-public-egress-sgr
resource "aws_security_group_rule" "nat_egress_all_inet" {
  type              = "egress"
  security_group_id = aws_security_group.nat_instance.id
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
  description       = "Allow all outbound traffic to Internet"
}

###############
# DB Instance SG
###############

# Ingress: DB port from Fargate demo
resource "aws_security_group_rule" "db_ingress_1433_from_fargate_demo" {
  type                     = "ingress"
  security_group_id        = aws_security_group.db_instance.id
  protocol                 = "tcp"
  from_port                = 1433
  to_port                  = 1433
  source_security_group_id = aws_security_group.fargate_demo.id
  description              = "Allow Fargate demo - DB instance (TCP/1433)"
}

# Egress: DB -> ANY
# Reason:
# - The DB instance lives fully inside private subnets
# - DB egress 0.0.0.0/0 is required so outbound traffic flows through NAT
# - No inbound exposure exists; outbound is NAT-routed and controlled
#tfsec:ignore:aws-ec2-no-public-egress-sgr
resource "aws_security_group_rule" "db_egress_any" {
  type              = "egress"
  security_group_id = aws_security_group.db_instance.id
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
  description       = "DB outbound to Internet via NAT"
}


#################
# Fargate Demo SG
#################

# Ingress: demo port from ALB
resource "aws_security_group_rule" "fargate_demo_ingress_from_alb" {
  type                     = "ingress"
  security_group_id        = aws_security_group.fargate_demo.id
  protocol                 = "tcp"
  from_port                = local.port_demo
  to_port                  = local.port_demo
  source_security_group_id = aws_security_group.alb_demo.id
  description              = "Allow ALB - Fargate demo (TCP demo port)"
}

resource "aws_security_group_rule" "fargate_demo_egress_to_db" {
  type                     = "egress"
  security_group_id        = aws_security_group.fargate_demo.id
  protocol                 = "tcp"
  from_port                = 1433
  to_port                  = 1433
  source_security_group_id = aws_security_group.db_instance.id
  description              = "Allow Fargate demo - DB instance (TCP/1433)"
}

# Reason:
# - Fargate tasks are in private subnets with route 0.0.0.0/0 -> NAT
# - Security Group egress 0.0.0.0/0 is required for NAT-based outbound access
#tfsec:ignore:aws-ec2-no-public-egress-sgr
resource "aws_security_group_rule" "fargate_egress_any" {
  type              = "egress"
  security_group_id = aws_security_group.fargate_demo.id
  protocol          = "-1"
  from_port         = 0
  to_port           = 0
  cidr_blocks       = ["0.0.0.0/0"]
  description       = "Fargate outbound to Internet via NAT"
}

