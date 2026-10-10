locals {
  name = "demo-dev-edge"

  tags = {
    Project     = "demo"
    Environment = "dev"
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
