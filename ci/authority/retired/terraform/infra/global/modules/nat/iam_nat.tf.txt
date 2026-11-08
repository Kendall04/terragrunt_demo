# ─────────────────────────────────────────────────────────────
# IAM Role and Instance Profile for NAT Instances
# - Allows the NAT EC2 instance to:
#     * Manage its own Elastic IP association
#     * Modify instance attributes
#     * Disable source/destination check
#     * Perform EC2 Describe calls required by auto-healing logic
# - Instance Profile is attached at launch time via Launch Template.
# ─────────────────────────────────────────────────────────────

data "aws_iam_policy_document" "nat_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "nat" {
  name               = "${var.name}-nat-role"
  assume_role_policy = data.aws_iam_policy_document.nat_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "nat_inline" {
  statement {
    sid    = "Ec2DescribeForNat"
    effect = "Allow"
    actions = [
      "ec2:DescribeInstances",
      "ec2:DescribeRouteTables",
      "ec2:DescribeNetworkInterfaces"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_policy" "nat" {
  name   = "${var.name}-nat-policy"
  policy = data.aws_iam_policy_document.nat_inline.json
}

resource "aws_iam_role_policy_attachment" "nat_attach" {
  role       = aws_iam_role.nat.name
  policy_arn = aws_iam_policy.nat.arn
}

resource "aws_iam_instance_profile" "nat" {
  name = "${var.name}-nat-instance-profile"
  role = aws_iam_role.nat.name
  tags = var.tags
}
