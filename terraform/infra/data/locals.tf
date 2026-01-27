locals {
  name = "${var.project}-${var.env}-data"

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
