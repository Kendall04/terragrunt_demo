
resource "aws_lb_target_group" "blue" {
  name        = "demo-dev-blue"
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
  name        = "demo-dev-green"
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
