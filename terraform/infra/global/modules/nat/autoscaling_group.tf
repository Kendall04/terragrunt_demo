# ─────────────────────────────────────────────────────────────
# Auto Scaling Groups for NAT Instances (one per Availability Zone)
# - Ensures one NAT instance per AZ (high availability across zones)
# - Using health_check_type = EC2; for faster recovery you can combine
#   with CloudWatch alarms on instance status check failures.
# - Force delete enabled for clean teardown in demo environments.
# ─────────────────────────────────────────────────────────────

resource "aws_autoscaling_group" "nat_a" {
  name                = "${var.name}-asg-nat-a"
  max_size            = 1
  min_size            = 1
  desired_capacity    = 1
  health_check_type   = "EC2"
  vpc_zone_identifier = [var.subnet_a_id]
  force_delete        = true

  launch_template {
    id      = aws_launch_template.nat_a.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${var.name}-nat-a"
    propagate_at_launch = true
  }
  tag {
    key                 = "Role"
    value               = "nat"
    propagate_at_launch = true
  }
  tag {
    key                 = "Group"
    value               = "a"
    propagate_at_launch = true
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    module.lambda_assign_eip,
    module.lambda_change_rt,
    module.lambda_disable_sdc,
    aws_cloudwatch_event_rule.ec2_running,
    aws_cloudwatch_event_target.t_assign_eip,
    aws_cloudwatch_event_target.t_change_rt,
    aws_cloudwatch_event_target.t_disable_sdc,
  ]
}

resource "aws_autoscaling_group" "nat_b" {
  name                = "${var.name}-asg-nat-b"
  max_size            = 1
  min_size            = 1
  desired_capacity    = 1
  health_check_type   = "EC2"
  vpc_zone_identifier = [var.subnet_b_id]
  force_delete        = true

  launch_template {
    id      = aws_launch_template.nat_b.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "${var.name}-nat-b"
    propagate_at_launch = true
  }
  tag {
    key                 = "Role"
    value               = "nat"
    propagate_at_launch = true
  }
  tag {
    key                 = "Group"
    value               = "b"
    propagate_at_launch = true
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    module.lambda_assign_eip,
    module.lambda_change_rt,
    module.lambda_disable_sdc,
    aws_cloudwatch_event_rule.ec2_running,
    aws_cloudwatch_event_target.t_assign_eip,
    aws_cloudwatch_event_target.t_change_rt,
    aws_cloudwatch_event_target.t_disable_sdc,
  ]
}
