locals {
  account_root_arn = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
}
