# Security Module - Security Groups and IAM

# ==================== ALB SECURITY GROUP ====================
resource "aws_security_group" "alb" {
  name_prefix = "${var.environment}-alb-"
  description = "Security group for Application Load Balancer"
  vpc_id      = var.vpc_id
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-alb-sg"
    }
  )
}

resource "aws_security_group_rule" "alb_http_ingress" {
  type              = "ingress"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  cidr_blocks       = var.allowed_cidr_blocks
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from allowed IPs"
}

resource "aws_security_group_rule" "alb_https_ingress" {
  type              = "ingress"
  from_port         = 443
  to_port           = 443
  protocol          = "tcp"
  cidr_blocks       = var.allowed_cidr_blocks
  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from allowed IPs"
}

resource "aws_security_group_rule" "alb_flower_ingress" {
  type              = "ingress"
  from_port         = 5555
  to_port           = 5555
  protocol          = "tcp"
  cidr_blocks       = var.allowed_cidr_blocks
  security_group_id = aws_security_group.alb.id
  description       = "Flower UI from allowed IPs"
}

resource "aws_security_group_rule" "alb_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.alb.id
  description       = "Allow all outbound"
}

# ==================== EC2 SECURITY GROUP ====================
resource "aws_security_group" "ec2" {
  name_prefix = "${var.environment}-ec2-"
  description = "Security group for EC2 instances"
  vpc_id      = var.vpc_id
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-ec2-sg"
    }
  )
}

resource "aws_security_group_rule" "ec2_ssh_ingress" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = var.ssh_allowed_ips
  security_group_id = aws_security_group.ec2.id
  description       = "SSH from allowed IPs"
}

resource "aws_security_group_rule" "ec2_api_from_alb" {
  type                     = "ingress"
  from_port                = 8000
  to_port                  = 8000
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
  security_group_id        = aws_security_group.ec2.id
  description              = "API traffic from ALB"
}

resource "aws_security_group_rule" "ec2_flower_from_alb" {
  type                     = "ingress"
  from_port                = 5555
  to_port                  = 5555
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
  security_group_id        = aws_security_group.ec2.id
  description              = "Flower traffic from ALB"
}

resource "aws_security_group_rule" "ec2_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.ec2.id
  description       = "Allow all outbound"
}

# ==================== RDS SECURITY GROUP ====================
resource "aws_security_group" "rds" {
  name_prefix = "${var.environment}-rds-"
  description = "Security group for RDS PostgreSQL"
  vpc_id      = var.vpc_id
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-rds-sg"
    }
  )
}

resource "aws_security_group_rule" "rds_postgres_from_ec2" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.ec2.id
  security_group_id        = aws_security_group.rds.id
  description              = "PostgreSQL from EC2"
}

resource "aws_security_group_rule" "rds_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.rds.id
  description       = "Allow all outbound"
}

# ==================== REDIS SECURITY GROUP ====================
resource "aws_security_group" "redis" {
  name_prefix = "${var.environment}-redis-"
  description = "Security group for ElastiCache Redis"
  vpc_id      = var.vpc_id
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-redis-sg"
    }
  )
}

resource "aws_security_group_rule" "redis_from_ec2" {
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.ec2.id
  security_group_id        = aws_security_group.redis.id
  description              = "Redis from EC2"
}

resource "aws_security_group_rule" "redis_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.redis.id
  description       = "Allow all outbound"
}

# ==================== IAM ROLES ====================

# EC2 Instance Role
resource "aws_iam_role" "ec2" {
  name = "${var.environment}-ec2-role"
  
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
  
  tags = var.tags
}

# EC2 Instance Profile
resource "aws_iam_instance_profile" "ec2" {
  name = "${var.environment}-ec2-profile"
  role = aws_iam_role.ec2.name
}

# ECR Read Policy
resource "aws_iam_role_policy_attachment" "ec2_ecr" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# CloudWatch Logs Policy
resource "aws_iam_role_policy_attachment" "ec2_cloudwatch" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# SSM Policy for Session Manager
resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Custom policy for Secrets Manager (if needed)
resource "aws_iam_role_policy" "ec2_secrets" {
  count = var.enable_secrets_manager ? 1 : 0
  name  = "${var.environment}-ec2-secrets"
  role  = aws_iam_role.ec2.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:*:*:secret:${var.environment}-*"
      }
    ]
  })
}