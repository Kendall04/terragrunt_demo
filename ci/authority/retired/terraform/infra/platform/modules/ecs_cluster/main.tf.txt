# ---------------------------------------------------------------------------
# ECS Cluster
# Creates a standard ECS cluster with Container Insights enabled for
# monitoring and CloudWatch metrics.
# ---------------------------------------------------------------------------
resource "aws_ecs_cluster" "this" {
  name = var.name

  # Enable detailed CloudWatch metrics
  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = var.tags
}

# ---------------------------------------------------------------------------
# ECS Capacity Providers
# Optional configuration that enables FARGATE and FARGATE_SPOT as
# capacity providers. This allows for more flexible scaling strategies.
# ---------------------------------------------------------------------------
resource "aws_ecs_cluster_capacity_providers" "cp" {
  count              = var.enable_capacity_providers ? 1 : 0
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    base              = var.fargate_base
    weight            = 1
  }
}
