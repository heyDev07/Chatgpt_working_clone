resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}/backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "frontend" {
  name                 = "${var.project_name}/frontend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

locals {
  # Expires untagged images once more than 10 are kept, so failed/superseded builds don't
  # accumulate storage cost indefinitely - tagged (real, deployed) images are untouched.
  ecr_keep_last_10_untagged = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Expire untagged images beyond the most recent 10"
      selection = {
        tagStatus   = "untagged"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy     = local.ecr_keep_last_10_untagged
}

resource "aws_ecr_lifecycle_policy" "frontend" {
  repository = aws_ecr_repository.frontend.name
  policy     = local.ecr_keep_last_10_untagged
}
