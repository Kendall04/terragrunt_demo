output "api_id" {
  description = "ID of the HTTP API Gateway."
  value       = aws_apigatewayv2_api.http.id
}

output "api_endpoint" {
  description = "Public endpoint of the HTTP API Gateway."
  value       = aws_apigatewayv2_api.http.api_endpoint
}
