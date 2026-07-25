# Secrets Manager holds the values app/config/settings.py reads from backend/.env locally -
# ECS task definitions reference these by ARN (see ecs.tf's `secrets` blocks) rather than baking
# them into the task definition's plain-text `environment` block, which would otherwise be
# visible to anyone with ecs:DescribeTaskDefinition.
resource "aws_secretsmanager_secret" "db_password" {
  name = "${var.project_name}/db-password"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = var.db_password
}

resource "aws_secretsmanager_secret" "jwt_secret_key" {
  name = "${var.project_name}/jwt-secret-key"
}

resource "aws_secretsmanager_secret_version" "jwt_secret_key" {
  secret_id     = aws_secretsmanager_secret.jwt_secret_key.id
  secret_string = var.jwt_secret_key
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  name = "${var.project_name}/openai-api-key"
}

resource "aws_secretsmanager_secret_version" "openai_api_key" {
  secret_id     = aws_secretsmanager_secret.openai_api_key.id
  secret_string = var.openai_api_key
}

resource "aws_secretsmanager_secret" "gemini_api_key" {
  name = "${var.project_name}/gemini-api-key"
}

resource "aws_secretsmanager_secret_version" "gemini_api_key" {
  secret_id     = aws_secretsmanager_secret.gemini_api_key.id
  secret_string = var.gemini_api_key
}

resource "aws_secretsmanager_secret" "tavily_api_key" {
  name = "${var.project_name}/tavily-api-key"
}

resource "aws_secretsmanager_secret_version" "tavily_api_key" {
  secret_id     = aws_secretsmanager_secret.tavily_api_key.id
  secret_string = var.tavily_api_key
}

resource "aws_secretsmanager_secret" "sql_demo_db_password" {
  name = "${var.project_name}/sql-demo-db-password"
}

resource "aws_secretsmanager_secret_version" "sql_demo_db_password" {
  secret_id     = aws_secretsmanager_secret.sql_demo_db_password.id
  secret_string = var.sql_demo_db_password
}
