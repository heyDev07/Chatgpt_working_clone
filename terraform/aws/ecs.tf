resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}/backend"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "frontend" {
  name              = "/ecs/${var.project_name}/frontend"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "qdrant" {
  name              = "/ecs/${var.project_name}/qdrant"
  retention_in_days = 14
}

# Private DNS namespace (AWS Cloud Map) so the backend can reach Qdrant at a stable hostname
# (qdrant.ai-assistant.local) instead of an ECS task's private IP, which changes every time the
# task restarts or redeploys - the same problem docker-compose's service-name DNS solves locally.
resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.project_name}.local"
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "qdrant" {
  name = "qdrant"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      ttl  = 10
      type = "A"
    }
    routing_policy = "MULTIVALUE"
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# --- Qdrant --------------------------------------------------------------------------------
resource "aws_ecs_task_definition" "qdrant" {
  family                   = "${var.project_name}-qdrant"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  volume {
    name = "qdrant-storage"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.qdrant.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.qdrant.id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "qdrant"
    image     = "qdrant/qdrant:latest"
    essential = true
    portMappings = [
      { containerPort = 6333, protocol = "tcp" },
      { containerPort = 6334, protocol = "tcp" },
    ]
    mountPoints = [{
      sourceVolume  = "qdrant-storage"
      containerPath = "/qdrant/storage"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.qdrant.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "qdrant"
      }
    }
  }])
}

resource "aws_ecs_service" "qdrant" {
  name            = "${var.project_name}-qdrant"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.qdrant.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.qdrant.id]
  }

  service_registries {
    registry_arn = aws_service_discovery_service.qdrant.arn
  }
}

# --- Backend ---------------------------------------------------------------------------------
resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  # 1 vCPU / 2GB - the browser-automation tool (Phase 9f) runs a real headless Chromium
  # subprocess per turn that uses one, so this needs meaningfully more than a bare API server.
  cpu                = 1024
  memory             = 2048
  execution_role_arn = aws_iam_role.ecs_task_execution.arn
  task_role_arn      = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name         = "backend"
    image        = local.backend_image
    essential    = true
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]
    environment = [
      { name = "DATABASE_URL", value = "postgresql+asyncpg://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}:5432/${var.db_name}" },
      { name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0" },
      { name = "QDRANT_URL", value = "http://qdrant.${var.project_name}.local:6333" },
      # Empty, not omitted - app/storage/s3_client.py only skips passing endpoint_url to boto3
      # (falling back to real AWS S3 resolution) when this is falsy. Leaving the key out
      # entirely would fall back to Settings' own MinIO-pointing local default instead.
      { name = "S3_ENDPOINT_URL", value = "" },
      { name = "S3_BUCKET", value = aws_s3_bucket.documents.bucket },
      { name = "ENVIRONMENT", value = var.environment },
      { name = "CORS_ORIGINS", value = "http://${aws_lb.main.dns_name}" },
    ]
    secrets = [
      { name = "JWT_SECRET_KEY", valueFrom = aws_secretsmanager_secret.jwt_secret_key.arn },
      { name = "OPENAI_API_KEY", valueFrom = aws_secretsmanager_secret.openai_api_key.arn },
      { name = "GEMINI_API_KEY", valueFrom = aws_secretsmanager_secret.gemini_api_key.arn },
      { name = "TAVILY_API_KEY", valueFrom = aws_secretsmanager_secret.tavily_api_key.arn },
      { name = "SQL_DEMO_DB_PASSWORD", valueFrom = aws_secretsmanager_secret.sql_demo_db_password.arn },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.backend.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "backend"
      }
    }
  }])
}

resource "aws_ecs_service" "backend" {
  name            = "${var.project_name}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.backend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.backend.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.backend.arn
    container_name   = "backend"
    container_port   = 8000
  }

  # Qdrant needs to be discoverable before the backend's own startup lifespan (which checks
  # Qdrant's collection) runs - not a hard dependency ECS enforces, but declared for clarity.
  depends_on = [aws_ecs_service.qdrant]
}

# --- Frontend ---------------------------------------------------------------------------------
resource "aws_ecs_task_definition" "frontend" {
  family                   = "${var.project_name}-frontend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([{
    name         = "frontend"
    image        = local.frontend_image
    essential    = true
    portMappings = [{ containerPort = 3000, protocol = "tcp" }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.frontend.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "frontend"
      }
    }
  }])
}

resource "aws_ecs_service" "frontend" {
  name            = "${var.project_name}-frontend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.frontend.arn
  desired_count   = var.frontend_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.frontend.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frontend.arn
    container_name   = "frontend"
    container_port   = 3000
  }
}

locals {
  # Falls back to "the ECR repo this config just created, :latest tag" when var.backend_image /
  # var.frontend_image aren't set - lets `terraform apply` succeed on a first run (to create the
  # ECR repos an image can then be pushed to) without already having an image to point at.
  backend_image  = var.backend_image != "" ? var.backend_image : "${aws_ecr_repository.backend.repository_url}:latest"
  frontend_image = var.frontend_image != "" ? var.frontend_image : "${aws_ecr_repository.frontend.repository_url}:latest"
}
