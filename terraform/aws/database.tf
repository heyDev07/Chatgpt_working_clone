resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnets"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "${var.project_name}-db-subnets" }
}

resource "aws_db_instance" "postgres" {
  identifier     = "${var.project_name}-postgres"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100 # storage autoscaling cap - avoids a surprise unbounded bill
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  # A demo/portfolio deployment's default should favor "don't leave an orphaned bill running" -
  # skip_final_snapshot is wrong for anything holding real user data long-term; flip both before
  # this ever holds data worth keeping.
  skip_final_snapshot = true
  deletion_protection = false

  backup_retention_period = 1

  tags = { Name = "${var.project_name}-postgres" }
}
