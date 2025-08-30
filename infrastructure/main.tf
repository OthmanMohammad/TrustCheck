# TrustCheck AWS Infrastructure

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

# ==================== PROVIDER ====================
provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "TrustCheck"
      Environment = var.environment
      ManagedBy   = "Terraform"
      CostCenter  = "Development"
    }
  }
}

# ==================== VARIABLES ====================
variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "db_password" {
  description = "RDS PostgreSQL password"
  type        = string
  sensitive   = true
}

variable "redis_auth_token" {
  description = "ElastiCache Redis auth token"
  type        = string
  sensitive   = true
  default     = ""  # Optional for now
}

variable "secret_key" {
  description = "Application secret key"
  type        = string
  sensitive   = true
}

# ==================== DATA SOURCES ====================
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]
  
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
}

# ==================== NETWORKING ====================
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name = "trustcheck-vpc"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  
  tags = {
    Name = "trustcheck-igw"
  }
}

# Public Subnets for ALB and EC2
resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  map_public_ip_on_launch = true
  
  tags = {
    Name = "trustcheck-public-${count.index + 1}"
    Type = "Public"
  }
}

# Private Subnets for RDS and ElastiCache
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 10}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  tags = {
    Name = "trustcheck-private-${count.index + 1}"
    Type = "Private"
  }
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  
  tags = {
    Name = "trustcheck-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ==================== SECURITY GROUPS ====================
resource "aws_security_group" "alb" {
  name        = "trustcheck-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP from anywhere"
  }
  
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS from anywhere"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
  
  tags = {
    Name = "trustcheck-alb-sg"
  }
}

resource "aws_security_group" "ec2" {
  name        = "trustcheck-ec2-sg"
  description = "Security group for EC2 instances"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port       = 22
    to_port         = 22
    protocol        = "tcp"
    cidr_blocks     = ["0.0.0.0/0"]  # Restrict this to your IP in production
    description     = "SSH access"
  }
  
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "API from ALB"
  }
  
  ingress {
    from_port       = 5555
    to_port         = 5555
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "Flower from ALB"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }
  
  tags = {
    Name = "trustcheck-ec2-sg"
  }
}

resource "aws_security_group" "rds" {
  name        = "trustcheck-rds-sg"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
    description     = "PostgreSQL from EC2"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "trustcheck-rds-sg"
  }
}

resource "aws_security_group" "elasticache" {
  name        = "trustcheck-elasticache-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = aws_vpc.main.id
  
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
    description     = "Redis from EC2"
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Name = "trustcheck-elasticache-sg"
  }
}

# ==================== RDS POSTGRESQL ====================
resource "aws_db_subnet_group" "main" {
  name       = "trustcheck-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  
  tags = {
    Name = "trustcheck-db-subnet-group"
  }
}

resource "aws_db_instance" "postgres" {
  identifier     = "trustcheck-db"
  engine         = "postgres"
  engine_version = "15"
  
  instance_class        = "db.t3.micro"  # Smallest instance
  allocated_storage     = 20             # Minimum storage
  storage_type          = "gp3"
  storage_encrypted     = true
  
  db_name  = "trustcheck"
  username = "trustcheck_user"
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  skip_final_snapshot       = true  # Set to false in real production
  deletion_protection       = false # Set to true in real production
  backup_retention_period   = 1     # Minimum backups to save cost
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:00-sun:05:00"
  
  # Cost optimization
  enabled_cloudwatch_logs_exports = []  # Disable to save cost
  performance_insights_enabled    = false
  monitoring_interval             = 0
  
  tags = {
    Name = "trustcheck-postgres"
  }
}

# ==================== ELASTICACHE REDIS ====================
resource "aws_elasticache_subnet_group" "main" {
  name       = "trustcheck-cache-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  
  tags = {
    Name = "trustcheck-cache-subnet-group"
  }
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "trustcheck-redis"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.t3.micro"  # Smallest instance
  num_cache_nodes      = 1                 # Single node to save cost
  parameter_group_name = "default.redis7"
  
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.elasticache.id]
  
  # Cost optimization
  snapshot_retention_limit = 0  # No snapshots
  notification_topic_arn   = ""
  
  tags = {
    Name = "trustcheck-redis"
  }
}

# ==================== EC2 INSTANCE ====================
resource "aws_key_pair" "main" {
  key_name   = "trustcheck-key"
  public_key = file("~/.ssh/id_rsa.pub")  # You'll need to generate this
}

resource "aws_iam_role" "ec2" {
  name = "trustcheck-ec2-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ec2_ecr" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "ec2_cloudwatch" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_instance_profile" "ec2" {
  name = "trustcheck-ec2-profile"
  role = aws_iam_role.ec2.name
}

# User data script for EC2
locals {
  user_data = templatefile("${path.module}/user_data.sh", {
    db_host      = aws_db_instance.postgres.address
    db_password  = var.db_password
    redis_host   = aws_elasticache_cluster.redis.cache_nodes[0].address
    secret_key   = var.secret_key
    ecr_uri      = aws_ecr_repository.main.repository_url
    aws_region   = var.aws_region
  })
}

resource "aws_instance" "app" {
  ami           = data.aws_ami.amazon_linux_2.id
  instance_type = "t3.small"  # Slightly bigger than micro for better performance
  
  key_name               = aws_key_pair.main.key_name
  vpc_security_group_ids = [aws_security_group.ec2.id]
  subnet_id              = aws_subnet.public[0].id
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  
  root_block_device {
    volume_type = "gp3"
    volume_size = 20  # Minimum needed for Docker
    encrypted   = true
  }
  
  user_data = local.user_data
  
  # Enable detailed monitoring (costs extra but useful)
  monitoring = false  # Set to true if you want CloudWatch metrics
  
  tags = {
    Name = "trustcheck-app"
  }
}

# ==================== APPLICATION LOAD BALANCER ====================
resource "aws_lb" "main" {
  name               = "trustcheck-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  
  enable_deletion_protection = false  # Set to true in production
  enable_http2               = true
  
  tags = {
    Name = "trustcheck-alb"
  }
}

resource "aws_lb_target_group" "api" {
  name     = "trustcheck-api-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }
  
  tags = {
    Name = "trustcheck-api-tg"
  }
}

resource "aws_lb_target_group_attachment" "api" {
  target_group_arn = aws_lb_target_group.api.arn
  target_id        = aws_instance.app.id
  port             = 8000
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# ==================== ECR REPOSITORY ====================
resource "aws_ecr_repository" "main" {
  name                 = "trustcheck"
  image_tag_mutability = "MUTABLE"
  
  image_scanning_configuration {
    scan_on_push = true
  }
  
  tags = {
    Name = "trustcheck-ecr"
  }
}

resource "aws_ecr_lifecycle_policy" "main" {
  repository = aws_ecr_repository.main.name
  
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ==================== CLOUDWATCH ====================
resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/ec2/trustcheck"
  retention_in_days = 3  # Minimum retention to save cost
  
  tags = {
    Name = "trustcheck-logs"
  }
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "trustcheck-dashboard"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/EC2", "CPUUtilization", { stat = "Average" }],
            ["AWS/RDS", "DatabaseConnections", { stat = "Average" }],
            ["AWS/ElastiCache", "CPUUtilization", { stat = "Average" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Resource Utilization"
        }
      }
    ]
  })
}

# ==================== OUTPUTS ====================
output "alb_dns" {
  value       = aws_lb.main.dns_name
  description = "Load balancer DNS name"
}

output "ec2_public_ip" {
  value       = aws_instance.app.public_ip
  description = "EC2 instance public IP"
}

output "rds_endpoint" {
  value       = aws_db_instance.postgres.endpoint
  description = "RDS PostgreSQL endpoint"
}

output "redis_endpoint" {
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
  description = "ElastiCache Redis endpoint"
}

output "ecr_repository_url" {
  value       = aws_ecr_repository.main.repository_url
  description = "ECR repository URL"
}

output "app_urls" {
  value = {
    api     = "http://${aws_lb.main.dns_name}"
    docs    = "http://${aws_lb.main.dns_name}/docs"
    health  = "http://${aws_lb.main.dns_name}/health"
    flower  = "http://${aws_lb.main.dns_name}:5555"
  }
  description = "Application URLs"
}