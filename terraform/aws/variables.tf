variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used as a prefix for every resource this config creates"
  type        = string
  default     = "ai-assistant"
}

variable "environment" {
  description = "Deployment environment name (e.g. production, staging) - propagated to the ECS tasks' ENVIRONMENT variable, matching app/config/settings.py's Settings.environment"
  type        = string
  default     = "production"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zone_count" {
  description = "Number of AZs to spread subnets across - 2 is the minimum RDS/ElastiCache multi-AZ features need"
  type        = number
  default     = 2
}

variable "db_name" {
  description = "Postgres database name"
  type        = string
  default     = "ai_assistant"
}

variable "db_username" {
  description = "Postgres master username"
  type        = string
  default     = "ai_assistant"
}

variable "db_password" {
  description = "Postgres master password - pass via TF_VAR_db_password or a .tfvars file that is gitignored, never commit a real value here"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro" # smallest ARM-based Graviton class - fine for demo/low-traffic use
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
}

variable "jwt_secret_key" {
  description = "Secret used to sign JWTs - pass via TF_VAR_jwt_secret_key, never commit a real value"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI-compatible provider API key (see backend/app/config/settings.py OPENAI_BASE_URL for pointing this at OpenRouter etc.)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key" {
  description = "Google Gemini API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "tavily_api_key" {
  description = "Tavily API key for the web search MCP tool - optional, register_mcp_servers() treats a blank value as 'this server isn't configured', not an error"
  type        = string
  sensitive   = true
  default     = ""
}

variable "sql_demo_db_password" {
  description = "Password for the sql_demo_reader Postgres role the text-to-SQL tool connects as - must match what the app's own alembic migration (0eb2d0957976) creates that role with"
  type        = string
  sensitive   = true
}

variable "backend_image" {
  description = "Full backend container image URI (e.g. the ECR repo this config creates, tagged by the CI pipeline) - leave blank on first apply and the ECR repository output can be used to push an image before setting this"
  type        = string
  default     = ""
}

variable "frontend_image" {
  description = "Full frontend container image URI"
  type        = string
  default     = ""
}

variable "backend_desired_count" {
  description = "Number of backend Fargate tasks to run"
  type        = number
  default     = 1
}

variable "frontend_desired_count" {
  description = "Number of frontend Fargate tasks to run"
  type        = number
  default     = 1
}
