data "aws_caller_identity" "current" {}

# This bucket is account-level, not environment-specific. In the same-account
# demo topology dev/shared creates it and prod/shared references the same name.
#tfsec:ignore:aws-s3-enable-bucket-logging
resource "aws_s3_bucket" "release_artifacts" {
  count = var.create_release_artifacts_bucket ? 1 : 0

  bucket = local.release_artifacts_bucket_name
  tags   = local.tags
}

resource "aws_s3_bucket_public_access_block" "release_artifacts" {
  count = var.create_release_artifacts_bucket ? 1 : 0

  bucket = aws_s3_bucket.release_artifacts[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "release_artifacts" {
  count = var.create_release_artifacts_bucket ? 1 : 0

  bucket = aws_s3_bucket.release_artifacts[0].id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "release_artifacts" {
  count = var.create_release_artifacts_bucket ? 1 : 0

  bucket = aws_s3_bucket.release_artifacts[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "release_artifacts" {
  count = var.create_release_artifacts_bucket ? 1 : 0

  bucket = aws_s3_bucket.release_artifacts[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "release_artifacts" {
  count = var.create_release_artifacts_bucket ? 1 : 0

  bucket = aws_s3_bucket.release_artifacts[0].id

  rule {
    id     = "retain-release-history"
    status = "Enabled"

    filter {
      prefix = ""
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 365
    }
  }
}
