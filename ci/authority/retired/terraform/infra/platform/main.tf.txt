# ---------------------------------------------------------------------------
# ECS Cluster Module
# Creates the main ECS cluster used by all Fargate services in the platform.
# Capacity providers can be optionally enabled.
# ---------------------------------------------------------------------------

module "ecs_cluster" {
  source = "./modules/ecs_cluster"

  name = "${local.name}-main-cluster"

  # Capacity provider configuration (FARGATE/FARGATE_SPOT)
  enable_capacity_providers = false
  fargate_base              = 100

  tags = local.tags
}
