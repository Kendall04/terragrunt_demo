resource "aws_cloudwatch_metric_alarm" "ecs_tasks_gap" {
  count = var.enable_alarms ? 1 : 0

  alarm_name        = "${var.name}-ecs-tasks-gap"
  alarm_description = "ECS desired tasks > running tasks (service not meeting desired count)"

  comparison_operator = "GreaterThanThreshold"
  threshold           = 0
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  treat_missing_data  = "missing"

  metric_query {
    id          = "m_running"
    return_data = false

    metric {
      namespace   = "ECS/ContainerInsights"
      metric_name = "RunningTaskCount"
      stat        = "Average"
      period      = 60

      dimensions = {
        ClusterName = var.cluster_arn != null ? split("/", var.cluster_arn)[1] : ""
        ServiceName = aws_ecs_service.this.name
      }
    }
  }

  metric_query {
    id          = "m_desired"
    return_data = false

    metric {
      namespace   = "ECS/ContainerInsights"
      metric_name = "DesiredTaskCount"
      stat        = "Average"
      period      = 60

      dimensions = {
        ClusterName = var.cluster_arn != null ? split("/", var.cluster_arn)[1] : ""
        ServiceName = aws_ecs_service.this.name
      }
    }
  }

  metric_query {
    id          = "e_gap"
    expression  = "IF((FILL(m_desired, -1) >= 0) AND (FILL(m_running, -1) >= 0), m_desired - m_running)"
    label       = "DesiredMinusRunning"
    return_data = true
  }

  alarm_actions = [var.alerts_topic_arn]
  ok_actions    = [var.alerts_topic_arn]

  tags = merge(var.tags, {
    Component = "ecs-service"
    Alarm     = "desired-vs-running-gap"
  })
}
