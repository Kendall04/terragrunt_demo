output "alerts_topic_arn" {
  value       = aws_sns_topic.alerts.arn
  description = "SNS topic ARN for CloudWatch alarm notifications"
}

output "alerts_email_configured" {
  value       = var.alert_email != null
  description = "Configured is not confirmed delivery; pending SNS confirmation cannot receive email"
}
