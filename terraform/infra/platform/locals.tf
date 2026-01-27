locals {
  name = "${var.project}-${var.env}-platform"

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
