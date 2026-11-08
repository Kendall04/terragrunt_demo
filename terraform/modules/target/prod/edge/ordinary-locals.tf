locals {
  name = "demo-prod-edge"

  tags = {
    Project     = "demo"
    Environment = "prod"
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
