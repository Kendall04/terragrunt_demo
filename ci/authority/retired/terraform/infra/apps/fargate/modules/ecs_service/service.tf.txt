# ECS Service (Fargate) with Cloud Map registration
resource "aws_ecs_service" "this" {
  name             = "${var.name}-svc"
  cluster          = var.cluster_arn
  task_definition  = aws_ecs_task_definition.this.arn
  desired_count    = var.desired_count
  launch_type      = "FARGATE"
  platform_version = var.platform_version

  enable_execute_command = var.enable_execute_command
  propagate_tags         = "SERVICE"
  scheduling_strategy    = "REPLICA"

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = var.security_group_ids
    assign_public_ip = var.assign_public_ip
  }

  # Optional load balancer attachment
  dynamic "load_balancer" {
    for_each = var.load_balancers
    content {
      target_group_arn = load_balancer.value.target_group_arn
      container_name   = load_balancer.value.container_name
      container_port   = load_balancer.value.container_port
    }
  }

  tags = var.tags

  lifecycle {
    ignore_changes = [
      desired_count,
      task_definition,
    ]
  }
}
