data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name = "demo-prod"

  tags = {
    Project     = "demo"
    Environment = "prod"
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }

  port_demo = 8080

  azs_all = data.aws_availability_zones.available.names
  azs     = slice(local.azs_all, 0, 2)
}
