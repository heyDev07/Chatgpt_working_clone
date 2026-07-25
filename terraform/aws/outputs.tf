output "alb_dns_name" {
  description = "Public URL for the app (HTTP only - see alb.tf/nginx.conf comments on why HTTPS isn't wired up here)"
  value       = "http://${aws_lb.main.dns_name}"
}

output "ecr_backend_repository_url" {
  description = "Push the backend image here, then set -var backend_image=<this>:<tag> on the next apply (or update the ECS service directly with `aws ecs update-service --force-new-deployment` after pushing :latest)"
  value       = aws_ecr_repository.backend.repository_url
}

output "ecr_frontend_repository_url" {
  description = "Push the frontend image here, same process as the backend repo"
  value       = aws_ecr_repository.frontend.repository_url
}

output "rds_endpoint" {
  description = "Postgres endpoint - run `alembic upgrade head` against this once, from anywhere with network access to it (e.g. a one-off ECS task, or a bastion), before the app is expected to work. Terraform provisions the empty database; it doesn't run the app's own migrations."
  value       = aws_db_instance.postgres.address
  sensitive   = true
}

output "redis_endpoint" {
  value     = aws_elasticache_cluster.redis.cache_nodes[0].address
  sensitive = true
}

output "s3_bucket_name" {
  value = aws_s3_bucket.documents.bucket
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}
