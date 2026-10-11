output "scale_down_lambda_arn" {
  description = "Lambda used by EventBridge to scale down the old color service."
  value       = module.scale_down_lambda.lambda_arn
}

output "scale_down_rule_name" {
  description = "EventBridge rule that triggers the scale-down Lambda after promotion."
  value       = local.scale_down_rule_name
}
