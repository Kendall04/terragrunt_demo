data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Task Role
resource "aws_iam_role" "task_role" {
  name               = "${var.name}-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

# Execution Role
resource "aws_iam_role" "execution_role" {
  name               = "${var.name}-exec-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
  tags               = var.tags
}

# Policy for Execution Role
resource "aws_iam_role_policy_attachment" "exec_base" {
  role       = aws_iam_role.execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Extras
resource "aws_iam_role_policy_attachment" "exec_extras" {
  for_each   = { for idx, arn in var.execution_policy_arns : idx => arn }
  role       = aws_iam_role.execution_role.name
  policy_arn = each.value
}

resource "aws_iam_role_policy_attachment" "task_extras" {
  for_each   = { for idx, arn in var.task_policy_arns : idx => arn }
  role       = aws_iam_role.task_role.name
  policy_arn = each.value
}
