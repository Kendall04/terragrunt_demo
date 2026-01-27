# ─────────────────────────────────────────────────────────────
# EventBridge Rule for NAT Auto-Healing
# - Triggers whenever an EC2 instance transitions to the "running" state.
# - Used to coordinate self-healing actions for NAT instances:
#     1. Assign the correct Elastic IP.
#     2. Update private route tables.
#     3. Disable Source/Destination Check.
# - Event targets: three independent Lambda functions handling each step.
# - Lambda permissions allow EventBridge to invoke the functions.
# ─────────────────────────────────────────────────────────────

resource "aws_cloudwatch_event_rule" "ec2_running" {
  name        = "${var.name}-on-ec2-running"
  description = "Dispara Lambdas para NAT cuando EC2 entra en running (ASG NAT)"
  event_pattern = jsonencode({
    "source" : ["aws.ec2"],
    "detail-type" : ["EC2 Instance State-change Notification"],
    "detail" : { "state" : ["running"] }
  })
  tags = var.tags
}

resource "aws_cloudwatch_event_target" "t_assign_eip" {
  rule = aws_cloudwatch_event_rule.ec2_running.name
  arn  = module.lambda_assign_eip.lambda_arn
}
resource "aws_cloudwatch_event_target" "t_change_rt" {
  rule = aws_cloudwatch_event_rule.ec2_running.name
  arn  = module.lambda_change_rt.lambda_arn
}
resource "aws_cloudwatch_event_target" "t_disable_sdc" {
  rule = aws_cloudwatch_event_rule.ec2_running.name
  arn  = module.lambda_disable_sdc.lambda_arn
}

resource "aws_lambda_permission" "allow_events_assign_eip" {
  statement_id  = "AllowExecFromEventsAssignEip"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_assign_eip.lambda_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ec2_running.arn
}
resource "aws_lambda_permission" "allow_events_change_rt" {
  statement_id  = "AllowExecFromEventsChangeRt"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_change_rt.lambda_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ec2_running.arn
}
resource "aws_lambda_permission" "allow_events_disable_sdc" {
  statement_id  = "AllowExecFromEventsDisableSdc"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_disable_sdc.lambda_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ec2_running.arn
}
