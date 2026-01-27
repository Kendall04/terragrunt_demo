# ─────────────────────────────────────────────────────────────
# Lambda Functions for NAT Auto-Healing Workflow
# - Three Python functions, each handling a specific NAT recovery task:
#
#   1. assign_eip  - Assign correct EIP to new NAT instance (per AZ)
#   2. change_rt   - Update route tables to point to the right NAT
#   3. disable_sdc - Disable Source/Destination check on NAT instance
#
# Now implemented via the generic lambda_function module.
# ─────────────────────────────────────────────────────────────

data "archive_file" "assign_eip_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/assign_eip.py"
  output_path = "${path.module}/lambda/assign_eip.zip"
}

data "archive_file" "change_rt_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/change_rt.py"
  output_path = "${path.module}/lambda/change_rt.zip"
}

data "archive_file" "disable_sdc_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/disable_sdc.py"
  output_path = "${path.module}/lambda/disable_sdc.zip"
}

resource "aws_cloudwatch_log_group" "lg_assign_eip" {
  name              = "/aws/lambda/${var.name}-assign-eip-lambda"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "lg_change_rt" {
  name              = "/aws/lambda/${var.name}-change-rt-lambda"
  retention_in_days = 14
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "lg_disable_sdc" {
  name              = "/aws/lambda/${var.name}-disable-sdc-lambda"
  retention_in_days = 14
  tags              = var.tags
}

# ─────────────────────────────────────────────────────────────
# Lambda 1: assign_eip
# ─────────────────────────────────────────────────────────────
module "lambda_assign_eip" {
  source = "../../../modules/lambda_function"

  # Base name → function_name = "${name}-lambda"
  name = "${var.name}-assign-eip"
  tags = var.tags

  role_arn = aws_iam_role.lambda_nat.arn

  # Deploy from local zip (no S3 needed)
  filename = data.archive_file.assign_eip_zip.output_path

  runtime     = "python3.12"
  handler     = "assign_eip.lambda_handler"
  memory_mb   = 128
  timeout_sec = 30

  environment_variables = {
    SUBNET_A_ID         = var.subnet_a_id
    SUBNET_B_ID         = var.subnet_b_id
    EIP_A_ALLOCATION_ID = aws_eip.nat_a.allocation_id
    EIP_B_ALLOCATION_ID = aws_eip.nat_b.allocation_id
  }

  # Log group with retention is pre-created above
  # (order does not really matter, Lambda will write logs there once invoked)
}

# ─────────────────────────────────────────────────────────────
# Lambda 2: change_rt
# ─────────────────────────────────────────────────────────────
module "lambda_change_rt" {
  source = "../../../modules/lambda_function"

  name = "${var.name}-change-rt"
  tags = var.tags

  role_arn = aws_iam_role.lambda_nat.arn

  filename = data.archive_file.change_rt_zip.output_path

  runtime     = "python3.12"
  handler     = "change_rt.lambda_handler"
  memory_mb   = 128
  timeout_sec = 30

  environment_variables = {
    ROUTE_TABLE_A_ID = var.route_table_a_id
    ROUTE_TABLE_B_ID = var.route_table_b_id
    SUBNET_A_ID      = var.subnet_a_id
    SUBNET_B_ID      = var.subnet_b_id
  }
}

# ─────────────────────────────────────────────────────────────
# Lambda 3: disable_sdc
# ─────────────────────────────────────────────────────────────
module "lambda_disable_sdc" {
  source = "../../../modules/lambda_function"

  name = "${var.name}-disable-sdc"
  tags = var.tags

  role_arn = aws_iam_role.lambda_nat.arn

  filename = data.archive_file.disable_sdc_zip.output_path

  runtime     = "python3.12"
  handler     = "disable_sdc.lambda_handler"
  memory_mb   = 128
  timeout_sec = 30

  environment_variables = {
    ASG_PREFIX = "${var.name}-asg-nat-"
  }
}
