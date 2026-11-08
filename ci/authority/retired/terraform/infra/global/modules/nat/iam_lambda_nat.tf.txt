# ─────────────────────────────────────────────────────────────
# IAM Role and Policy for NAT Auto-Healing Lambda Functions
# - Allows Lambda to manage routes, network interfaces, EIP assignment,
#   and instance attribute modifications required for NAT failover.
# - Grants minimal permissions for CloudWatch Logs.
# - This role is attached to all three NAT healing Lambdas.
# ─────────────────────────────────────────────────────────────

resource "aws_iam_role" "lambda_nat" {
  name = "${var.name}-lambda-nat-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })
  tags = var.tags
}

# Reason:
# - NAT auto-healing requires Associate/DisassociateAddress on EC2,
#   and these APIs do not support fine-grained resource scoping easily.
# - Actions are constrained to NAT-related workflows only.
#tfsec:ignore:aws-iam-no-policy-wildcards
resource "aws_iam_policy" "lambda_nat" {
  name = "${var.name}-lambda-nat-policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect : "Allow",
        Action : ["logs:CreateLogStream", "logs:PutLogEvents"],
        Resource : [
          aws_cloudwatch_log_group.lg_assign_eip.arn,
          aws_cloudwatch_log_group.lg_change_rt.arn,
          aws_cloudwatch_log_group.lg_disable_sdc.arn,
        ]
      },
      {
        Effect : "Allow",
        Action : [
          "autoscaling:DescribeAutoScalingGroups",
          "ec2:DescribeInstances",
          "ec2:DescribeRouteTables",
          "ec2:DescribeNetworkInterfaces"
        ],
        Resource : "*"
      },
      {
        Effect : "Allow",
        Action : [
          "ec2:ReplaceRoute",
          "ec2:CreateRoute"
        ],
        Resource : [
          local.route_table_a_arn,
          local.route_table_b_arn
        ]
      },
      {
        Effect : "Allow",
        Action : [
          "ec2:ModifyInstanceAttribute"
        ],
        Resource : local.nat_instance_arn_pattern,
        Condition : {
          "StringEquals" : {
            "aws:ResourceTag/Role" : "nat"
          }
        }
      },
      {
        Effect : "Allow",
        Action : [
          "ec2:AssociateAddress",
          "ec2:DisassociateAddress"
        ],
        Resource : "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_nat_attach" {
  role       = aws_iam_role.lambda_nat.name
  policy_arn = aws_iam_policy.lambda_nat.arn
}

resource "aws_iam_role_policy_attachment" "lambda_nat_basic_exec" {
  role       = aws_iam_role.lambda_nat.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
