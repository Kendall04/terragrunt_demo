locals {
  name = "demo-dev-platform"

  tags = {
    Project     = "demo"
    Environment = "dev"
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
