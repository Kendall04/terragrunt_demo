output "task_role_arn" {
  value       = aws_iam_role.task_role.arn
  description = "ARN of the ECS task role."
}

output "execution_role_arn" {
  value       = aws_iam_role.execution_role.arn
  description = "ARN of the ECS execution role."
}

output "service_name" {
  value       = aws_ecs_service.this.name
  description = "Name of the ECS service."
}

output "service_arn" {
  value       = aws_ecs_service.this.id
  description = "ARN of the ECS service."
}

output "task_definition_arn" {
  value       = aws_ecs_task_definition.this.arn
  description = "ARN of the task definition."
}
