resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-"
  description = "Internet-facing ALB - only ingress point into the whole VPC"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # 443 isn't opened here - no ACM certificate is provisioned (see alb.tf's comment on the same
  # reasoning as nginx.conf's commented-out TLS block: no real domain to issue one against in
  # this environment). Add an ingress block for 443 once acm.tf's certificate exists.

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-alb-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "backend" {
  name_prefix = "${var.project_name}-backend-"
  description = "Backend ECS tasks - only reachable from the ALB, not directly from the internet"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "API traffic from ALB"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Open egress: the backend calls out to OpenRouter/Gemini/Tavily/Pollinations.ai, pulls its
  # own container image, and (app/tools/browser.py) runs `npx @playwright/mcp` which resolves
  # against the npm registry at runtime - none of these are fixed IPs that could be allowlisted
  # narrowly without breaking whichever one changes IP ranges first.
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-backend-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "frontend" {
  name_prefix = "${var.project_name}-frontend-"
  description = "Frontend ECS tasks - only reachable from the ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "HTTP traffic from ALB"
    from_port       = 3000
    to_port         = 3000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-frontend-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "qdrant" {
  name_prefix = "${var.project_name}-qdrant-"
  description = "Qdrant ECS task - only reachable from the backend"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Qdrant REST/gRPC API from backend"
    from_port       = 6333
    to_port         = 6334
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-qdrant-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "qdrant_efs" {
  name_prefix = "${var.project_name}-qdrant-efs-"
  description = "EFS mount targets backing Qdrant's persistent storage - only reachable from the Qdrant task"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "NFS from Qdrant task"
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.qdrant.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-qdrant-efs-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-rds-"
  description = "RDS Postgres - only reachable from the backend"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Postgres from backend"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-rds-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "redis" {
  name_prefix = "${var.project_name}-redis-"
  description = "ElastiCache Redis - only reachable from the backend"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redis from backend"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.backend.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-redis-sg" }

  lifecycle {
    create_before_destroy = true
  }
}
