locals {
  name = "demo-dev-data"

  tags = {
    Project     = "demo"
    Environment = "dev"
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
