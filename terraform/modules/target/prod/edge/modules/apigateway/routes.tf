resource "aws_apigatewayv2_route" "routes" {
  for_each  = { for r in local.routes : r.key => r }
  api_id    = aws_apigatewayv2_api.http.id
  route_key = each.key

  target = "integrations/${aws_apigatewayv2_integration.alb_integration.id}"

  authorization_type = "NONE"
}
