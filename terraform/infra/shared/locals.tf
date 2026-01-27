locals {
  name = "${var.project}-${var.env}-shared"

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
