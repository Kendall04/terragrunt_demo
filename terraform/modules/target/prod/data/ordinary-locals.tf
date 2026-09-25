locals {
  name = "demo-prod-data"

  tags = {
    Project     = "demo"
    Environment = "prod"
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
