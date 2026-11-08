resource "aws_apigatewayv2_api" "http" {
  name                       = var.name
  protocol_type              = "HTTP"
  route_selection_expression = "$request.method $request.path"

  dynamic "cors_configuration" {
    for_each = length(var.cors_allowed_origins) > 0 ? [1] : []
    content {
      allow_credentials = false
      allow_headers = [
        "authorization",
        "content-type",
        "x-amz-date",
        "x-amz-security-token",
        "x-api-key",
      ]
      allow_methods = ["GET", "POST", "OPTIONS"]
      allow_origins = var.cors_allowed_origins
      max_age       = 3600
    }
  }

  tags = var.tags
}

resource "aws_apigatewayv2_integration" "alb_integration" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  payload_format_version = "1.0"
  timeout_milliseconds   = 30000

  connection_type = "VPC_LINK"
  connection_id   = var.vpc_link_id

  integration_uri = var.alb_listener_arn
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http.id
  name        = "$default"
  auto_deploy = true
  tags        = var.tags

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gw_access.arn
    format = jsonencode({
      requestId   = "$context.requestId"
      httpMethod  = "$context.httpMethod"
      path        = "$context.path"
      status      = "$context.status"
      ip          = "$context.identity.sourceIp"
      userAgent   = "$context.identity.userAgent"
      requestTime = "$context.requestTime"
      integration = "$context.integrationErrorMessage"
    })
  }
}

resource "aws_cloudwatch_log_group" "api_gw_access" {
  name              = "/aws/apigw/${var.name}-http-access"
  retention_in_days = 30
  tags              = var.tags
}
