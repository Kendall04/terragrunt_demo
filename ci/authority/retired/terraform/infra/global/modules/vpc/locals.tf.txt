# ─────────────────────────────────────────────────────────────
# Local CIDR definitions derived from the main VPC CIDR block
# - Creates deterministic /24 subnets for public and private networks
# - public0 / public1 used for load balancers, NAT instances
# - private0 / private1 used for ECS, EC2 workloads, and internal services
# ─────────────────────────────────────────────────────────────

locals {
  public0_cidr  = cidrsubnet(var.vpc_cidr, 8, 0)   # 10.0.0.0/24
  public1_cidr  = cidrsubnet(var.vpc_cidr, 8, 1)   # 10.0.1.0/24
  private0_cidr = cidrsubnet(var.vpc_cidr, 8, 100) # 10.0.100.0/24
  private1_cidr = cidrsubnet(var.vpc_cidr, 8, 101) # 10.0.101.0/24
}
