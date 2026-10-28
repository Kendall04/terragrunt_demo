# ─────────────────────────────────────────────────────────────
# BLUE/GREEN DEPLOYMENT — ALB Target Groups
#
# This module defines two independent Target Groups for a 
# Blue/Green deployment strategy:
#
#   - BLUE  : Active production service
#   - GREEN : Deployment candidate receiving the new release
#
# The Load Balancer will forward traffic to one TG at a time.
# ECS services register tasks into each TG using `target_type = ip`,
# required for Fargate with awsvpc networking.
#
# Health checks ensure that only healthy tasks receive traffic.
# These TGs are intentionally symmetrical for predictable swaps.
# ─────────────────────────────────────────────────────────────

resource "aws_lb_target_group" "blue" {
  name        = "${var.name}-blue-tg"
  vpc_id      = var.vpc_id
  protocol    = "HTTP"
  port        = var.demo_port
  target_type = "ip"

  health_check {
    enabled             = true
    interval            = 10
    timeout             = 6
    healthy_threshold   = 2
    unhealthy_threshold = 2
    protocol            = "HTTP"
    path                = var.demo_health_path
    matcher             = "200-399"
  }

  tags = merge(var.tags, {
    Deployment = "Blue"
  })
}

resource "aws_lb_target_group" "green" {
  name        = "${var.name}-green-tg"
  vpc_id      = var.vpc_id
  protocol    = "HTTP"
  port        = var.demo_port
  target_type = "ip"

  health_check {
    enabled             = true
    interval            = 10
    timeout             = 6
    healthy_threshold   = 2
    unhealthy_threshold = 2
    protocol            = "HTTP"
    path                = var.demo_health_path
    matcher             = "200-399"
  }

  tags = merge(var.tags, {
    Deployment = "Green"
  })
}
