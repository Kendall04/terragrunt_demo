resource "aws_iam_role" "scale_down_lambda" {
  name = "${local.scale_down_lambda_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "lambda.amazonaws.com" },
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_policy" "scale_down_lambda" {
  name = "${local.scale_down_lambda_name}-policy"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid      = "DescribeListener",
        Effect   = "Allow",
        Action   = ["elasticloadbalancing:DescribeListeners"],
        Resource = "*"
      },
      {
        Sid      = "DescribeServices",
        Effect   = "Allow",
        Action   = ["ecs:DescribeServices"],
        Resource = "*"
      },
      {
        Sid    = "UpdateServices",
        Effect = "Allow",
        Action = ["ecs:UpdateService"],
        Resource = [
          "arn:aws:ecs:${var.aws_region}:${local.account_id}:service/${var.cluster_name}/${module.demo_api_blue.service_name}",
          "arn:aws:ecs:${var.aws_region}:${local.account_id}:service/${var.cluster_name}/${module.demo_api_green.service_name}"
        ]
      },
      {
        Sid    = "ManageScaleDownRule",
        Effect = "Allow",
        Action = [
          "events:RemoveTargets",
          "events:DeleteRule"
        ],
        Resource = "arn:aws:events:${var.aws_region}:${local.account_id}:rule/${local.scale_down_rule_name}"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "scale_down_custom_attach" {
  role       = aws_iam_role.scale_down_lambda.name
  policy_arn = aws_iam_policy.scale_down_lambda.arn
}

resource "aws_iam_role_policy_attachment" "scale_down_basic_exec" {
  role       = aws_iam_role.scale_down_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
