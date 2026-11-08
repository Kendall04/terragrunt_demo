locals {
  name = "demo-prod-platform"

  tags = {
    Project     = "demo"
    Environment = "prod"
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
