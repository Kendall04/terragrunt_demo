resource "aws_cloudwatch_metric_alarm" "nat_a_inservice_low" {
  count               = contains(keys(var.protected_nat_launch), "a") ? 1 : 0
  alarm_name          = "${local.name}-nat-a-inservice-low"
  alarm_description   = "NAT-A ASG has no InService instances (egress from AZ-a likely broken)."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  period              = 60
  threshold           = 1
  statistic           = "Minimum"
  treat_missing_data  = "missing"

  namespace   = "AWS/AutoScaling"
  metric_name = "GroupInServiceInstances"
  dimensions = {
    AutoScalingGroupName = aws_autoscaling_group.wp5_nat["a"].name
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  tags = local.tags
}
resource "aws_cloudwatch_metric_alarm" "nat_a_capacity_gap" {
  count               = contains(keys(var.protected_nat_launch), "a") ? 1 : 0
  alarm_name          = "${local.name}-nat-a-capacity-gap"
  alarm_description   = "NAT-A DesiredCapacity > InServiceInstances (ASG can't satisfy capacity)."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 0
  treat_missing_data  = "missing"

  metric_query {
    id          = "desired"
    return_data = false
    metric {
      namespace   = "AWS/AutoScaling"
      metric_name = "GroupDesiredCapacity"
      period      = 60
      stat        = "Average"
      dimensions = {
        AutoScalingGroupName = aws_autoscaling_group.wp5_nat["a"].name
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
        AutoScalingGroupName = aws_autoscaling_group.wp5_nat["a"].name
      }
    }
  }

  metric_query {
    id          = "gap"
    expression  = "IF((FILL(desired, -1) >= 0) AND (FILL(inservice, -1) >= 0), desired - inservice)"
    label       = "CapacityGap"
    return_data = true
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  tags = local.tags
}
