locals {
  name = "${var.project}-${var.env}-shared"

  release_artifacts_bucket_name = coalesce(
    var.release_artifacts_bucket_name,
    "${var.project}-release-artifacts-${data.aws_caller_identity.current.account_id}",
  )

  shared_artifact_ecr_repository_name = coalesce(
    var.shared_artifact_ecr_repository_name,
    "${var.project}-shared-demo-ms",
  )

  tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
    Owner       = "kendall"
  }
}
