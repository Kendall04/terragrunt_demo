# -----------------------------
# NAT-A: InServiceInstances < 1
# -----------------------------
resource "aws_cloudwatch_metric_alarm" "nat_a_inservice_low" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.name}-nat-a-inservice-low"
  alarm_description   = "NAT-A ASG has no InService instances (egress from AZ-a likely broken)."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  period              = 60
  threshold           = 1
  statistic           = "Minimum"
  treat_missing_data  = "notBreaching"

  namespace   = "AWS/AutoScaling"
  metric_name = "GroupInServiceInstances"
  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.nat_a.name
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  tags = var.tags
}

# -----------------------------
# NAT-B: InServiceInstances < 1
# -----------------------------
resource "aws_cloudwatch_metric_alarm" "nat_b_inservice_low" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.name}-nat-b-inservice-low"
  alarm_description   = "NAT-B ASG has no InService instances (egress from AZ-b likely broken)."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  period              = 60
  threshold           = 1
  statistic           = "Minimum"
  treat_missing_data  = "notBreaching"

  namespace   = "AWS/AutoScaling"
  metric_name = "GroupInServiceInstances"
  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.nat_b.name
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  tags = var.tags
}








resource "aws_cloudwatch_metric_alarm" "nat_a_capacity_gap" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.name}-nat-a-capacity-gap"
  alarm_description   = "NAT-A DesiredCapacity > InServiceInstances (ASG can't satisfy capacity)."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 0
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "desired"
    return_data = false
    metric {
      namespace   = "AWS/AutoScaling"
      metric_name = "GroupDesiredCapacity"
      period      = 60
      stat        = "Average"
      dimensions = {
        AutoScalingGroupName = aws_autoscaling_group.nat_a.name
      }
    }
  }

  metric_query {
    id          = "inservice"
    return_data = false
    metric {
      namespace   = "AWS/AutoScaling"
      metric_name = "GroupInServiceInstances"
      period      = 60
      stat        = "Average"
      dimensions = {
        AutoScalingGroupName = aws_autoscaling_group.nat_a.name
      }
    }
  }

  metric_query {
    id          = "gap"
    expression  = "desired - inservice"
    label       = "CapacityGap"
    return_data = true
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "nat_b_capacity_gap" {
  count               = var.enable_alarms ? 1 : 0
  alarm_name          = "${var.name}-nat-b-capacity-gap"
  alarm_description   = "NAT-B DesiredCapacity > InServiceInstances (ASG can't satisfy capacity)."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 0
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "desired"
    return_data = false
    metric {
      namespace   = "AWS/AutoScaling"
      metric_name = "GroupDesiredCapacity"
      period      = 60
      stat        = "Average"
      dimensions = {
        AutoScalingGroupName = aws_autoscaling_group.nat_b.name
      }
    }
  }

  metric_query {
    id          = "inservice"
    return_data = false
    metric {
      namespace   = "AWS/AutoScaling"
      metric_name = "GroupInServiceInstances"
      period      = 60
      stat        = "Average"
      dimensions = {
        AutoScalingGroupName = aws_autoscaling_group.nat_b.name
      }
    }
  }

  metric_query {
    id          = "gap"
    expression  = "desired - inservice"
    label       = "CapacityGap"
    return_data = true
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  tags = var.tags
}
