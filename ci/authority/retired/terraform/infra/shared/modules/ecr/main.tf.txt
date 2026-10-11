# Creates one ECR repository per entry in var.repo_names.
resource "aws_ecr_repository" "repos" {
  for_each = toset(var.repo_names)

  name                 = each.key
  image_tag_mutability = local.mutability

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  tags = var.tags
}

# Lifecycle policy applied to each repository.
# Keeps only the last N images (var.lifecycle_keep), removing older ones
# to control storage costs.
resource "aws_ecr_lifecycle_policy" "repos" {
  for_each   = aws_ecr_repository.repos
  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last ${var.lifecycle_keep} images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.lifecycle_keep
        }
        action = { type = "expire" }
      }
    ]
  })
}
