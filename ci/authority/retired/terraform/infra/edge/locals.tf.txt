locals {
  name = "${var.project}-${var.env}-edge"

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
