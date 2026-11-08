# ECS Task Definition using Fargate
resource "aws_ecs_task_definition" "this" {
  family                   = coalesce(var.family, var.name)
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]

  cpu    = var.task_cpu
  memory = var.task_memory

  execution_role_arn    = aws_iam_role.execution_role.arn
  task_role_arn         = aws_iam_role.task_role.arn
  container_definitions = local.container_definitions

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  tags = var.tags
}
