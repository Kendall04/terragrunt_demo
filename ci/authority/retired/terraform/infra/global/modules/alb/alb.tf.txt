# ─────────────────────────────────────────────────────────────
# Internal Application Load Balancer
# - Internal (not internet-facing)
# - Placed in private subnets
# - Exposes HTTP endpoint for ECS services via ALB listener
# ─────────────────────────────────────────────────────────────

resource "aws_lb" "demo_internal_alb" {
  name               = "${var.name}-internal-alb"
  load_balancer_type = "application"
  internal           = true

  subnets         = var.subnet_ids
  security_groups = [var.sg_id]

  drop_invalid_header_fields = true

  # Recommended default: prevent accidental deletion
  enable_deletion_protection = false

  tags = merge(var.tags, { Name = "${var.name}-internal-alb" })
}

# ─────────────────────────────────────────────────────────────
# HTTP Listener for the ALB
# - Forwards traffic into the target group
# - Must use HTTP/HTTPS (ALB does NOT support TCP)
# ─────────────────────────────────────────────────────────────

# Reason:
# - This ALB is marked internal = true
# - It is deployed strictly in private subnets
# - It is reachable only through API Gateway VPC Link (private ENIs)
# - No public access ports exist
#tfsec:ignore:aws-elb-http-not-used
resource "aws_lb_listener" "demo_http_listener" {
  load_balancer_arn = aws_lb.demo_internal_alb.arn
  port              = var.demo_port
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.blue.arn
  }

  lifecycle {
    ignore_changes = [
      default_action
    ]
  }
}

resource "aws_lb_listener_rule" "candidate_rule" {
  listener_arn = aws_lb_listener.demo_http_listener.arn
  priority     = 100

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.green.arn
  }

  condition {
    path_pattern {
      values = ["/__candidate_dummy__"]
    }
  }

  lifecycle {
    ignore_changes = [
      action
    ]
  }
}
