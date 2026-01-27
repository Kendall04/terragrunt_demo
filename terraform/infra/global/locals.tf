data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  name = "${var.project}-${var.env}"

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }

  port_demo = 8080

  azs_all = data.aws_availability_zones.available.names
  azs     = slice(local.azs_all, 0, 2)
}
