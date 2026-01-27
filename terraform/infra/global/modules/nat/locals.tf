data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  nat_instance_arn_pattern = "arn:aws:ec2:${local.region}:${local.account_id}:instance/*"

  route_table_a_arn = "arn:aws:ec2:${local.region}:${local.account_id}:route-table/${var.route_table_a_id}"
  route_table_b_arn = "arn:aws:ec2:${local.region}:${local.account_id}:route-table/${var.route_table_b_id}"
}
