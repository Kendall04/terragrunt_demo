output "ecs_runtime_roles" { value = { for k, r in aws_iam_role.runtime : k => r.name } }
output "ecs_boundaries" { value = { for k, p in aws_iam_policy.ecs_boundary : k => p.name } }
output "ecs_policy_pairs_equal" { value = alltrue([for k in local.roles : aws_iam_policy.ecs_boundary[k].policy == aws_iam_role_policy.runtime[k].policy]) }
output "ecs_runtime_policy_documents" { value = local.ecs_runtime_policies }
output "ecs_handlers" { value = { for k, f in aws_lambda_function.runtime : k => f.handler } }
output "ecs_ingestion_enabled" { value = aws_lambda_event_source_mapping.reports.enabled }
output "ecs_schedule_states" { value = { for k, r in aws_cloudwatch_event_rule.tick : k => r.state } }

output "ecs_alarm_actions_enabled" { value = { for k, a in aws_cloudwatch_metric_alarm.errors : k => a.actions_enabled } }
