# Replaces MinIO for a real deployment - app/storage/s3_client.py already talks to any
# S3-compatible endpoint via aioboto3 (MinIO locally, for exactly this reason), so pointing it at
# real AWS S3 instead just means setting S3_ENDPOINT_URL to AWS's regional endpoint (or leaving
# boto3's own default resolution to handle it) - no code change needed.
resource "aws_s3_bucket" "documents" {
  bucket = "${var.project_name}-documents-${data.aws_caller_identity.current.account_id}"
  tags   = { Name = "${var.project_name}-documents" }
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_cors_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  cors_rule {
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = ["*"] # tighten to the real frontend origin once one exists
    allowed_headers = ["*"]
  }
}
