
module "ecs_cluster" {
  source = "./modules/ecs_cluster"

  name = "${local.name}-main-cluster"

  enable_capacity_providers = false
  fargate_base              = 100

  tags = local.tags
}
