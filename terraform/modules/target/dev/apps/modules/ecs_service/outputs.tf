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
