terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state by default - fine for a single operator getting started, but state holds
  # sensitive values (DB passwords end up in plan/state output) and doesn't support locking for
  # concurrent applies. Switch to an S3 backend + DynamoDB lock table before a second person (or
  # a CI pipeline) ever runs terraform apply against this:
  #
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "ai-assistant/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-locks"
  #   encrypt        = true
  # }
}
