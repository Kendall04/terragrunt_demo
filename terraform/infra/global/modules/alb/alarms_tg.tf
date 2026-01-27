resource "aws_cloudwatch_metric_alarm" "tg_blue_5xx" {
  alarm_name        = "${var.name}-tg-blue-5xx"
  alarm_description = "5XX errors from BLUE target group"

  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"

  dimensions = {
    LoadBalancer = aws_lb.demo_internal_alb.arn_suffix
    TargetGroup  = aws_lb_target_group.blue.arn_suffix
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  treat_missing_data = "notBreaching"
  tags               = merge(var.tags, { Deployment = "Blue" })
}

resource "aws_cloudwatch_metric_alarm" "tg_green_5xx" {
  alarm_name        = "${var.name}-tg-green-5xx"
  alarm_description = "5XX errors from GREEN target group"

  namespace           = "AWS/ApplicationELB"
  metric_name         = "HTTPCode_Target_5XX_Count"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 5
  comparison_operator = "GreaterThanOrEqualToThreshold"

  dimensions = {
    LoadBalancer = aws_lb.demo_internal_alb.arn_suffix
    TargetGroup  = aws_lb_target_group.green.arn_suffix
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  treat_missing_data = "notBreaching"
  tags               = merge(var.tags, { Deployment = "Green" })
}


resource "aws_cloudwatch_metric_alarm" "tg_blue_latency" {
  alarm_name        = "${var.name}-tg-blue-latency"
  alarm_description = "High latency on BLUE target group"

  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 1.5
  comparison_operator = "GreaterThanThreshold"

  dimensions = {
    LoadBalancer = aws_lb.demo_internal_alb.arn_suffix
    TargetGroup  = aws_lb_target_group.blue.arn_suffix
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  treat_missing_data = "notBreaching"
  tags               = merge(var.tags, { Deployment = "Blue" })
}

resource "aws_cloudwatch_metric_alarm" "tg_green_latency" {
  alarm_name        = "${var.name}-tg-green-latency"
  alarm_description = "High latency on GREEN target group"

  namespace           = "AWS/ApplicationELB"
  metric_name         = "TargetResponseTime"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 2
  threshold           = 1.5
  comparison_operator = "GreaterThanThreshold"

  dimensions = {
    LoadBalancer = aws_lb.demo_internal_alb.arn_suffix
    TargetGroup  = aws_lb_target_group.green.arn_suffix
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  treat_missing_data = "notBreaching"
  tags               = merge(var.tags, { Deployment = "Green" })
}
