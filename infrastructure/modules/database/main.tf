# Database Module - RDS PostgreSQL

# ==================== SUBNET GROUP ====================
resource "aws_db_subnet_group" "main" {
  name       = "${var.environment}-db-subnet-group"
  subnet_ids = var.subnet_ids
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-db-subnet-group"
    }
  )
}

# ==================== PARAMETER GROUP ====================
resource "aws_db_parameter_group" "main" {
  name   = "${var.environment}-postgres15-params"
  family = "postgres15"
  
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }
  
  parameter {
    name  = "log_statement"
    value = var.environment == "production" ? "all" : "none"
  }
  
  parameter {
    name  = "log_duration"
    value = "1"
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-db-params"
    }
  )
  
  lifecycle {
    create_before_destroy = true
  }
}

# ==================== RDS INSTANCE ====================
resource "aws_db_instance" "postgres" {
  identifier = "${var.environment}-trustcheck-db"
  
  # Engine
  engine               = "postgres"
  engine_version      = "15"
  
  # Instance
  instance_class       = var.db_instance_class
  allocated_storage    = var.db_allocated_storage
  storage_type         = "gp3"
  storage_encrypted    = true
  kms_key_id          = var.kms_key_id
  
  # Database
  db_name  = "trustcheck"
  username = "trustcheck_user"
  password = var.db_password
  port     = 5432
  
  # Network
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]
  publicly_accessible    = false
  
  # Parameters
  parameter_group_name = aws_db_parameter_group.main.name
  
  # Backup
  backup_retention_period   = var.backup_retention_period
  backup_window            = "03:00-04:00"
  maintenance_window       = "sun:04:00-sun:05:00"
  skip_final_snapshot      = var.environment != "production"
  final_snapshot_identifier = var.environment == "production" ? "${var.environment}-trustcheck-final-${formatdate("YYYY-MM-DD-hhmm", timestamp())}" : null
  deletion_protection      = var.deletion_protection
  
  # Performance Insights
  performance_insights_enabled    = var.environment == "production"
  performance_insights_retention_period = var.environment == "production" ? 7 : 0
  
  # Monitoring
  enabled_cloudwatch_logs_exports = var.environment == "production" ? ["postgresql"] : []
  monitoring_interval            = var.environment == "production" ? 60 : 0
  monitoring_role_arn           = var.environment == "production" ? aws_iam_role.rds_monitoring[0].arn : null
  
  # Auto Minor Version Upgrade
  auto_minor_version_upgrade = true
  apply_immediately         = var.environment != "production"
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-trustcheck-db"
    }
  )
  
  depends_on = [aws_db_parameter_group.main]
}

# ==================== MONITORING ROLE ====================
resource "aws_iam_role" "rds_monitoring" {
  count = var.environment == "production" ? 1 : 0
  name  = "${var.environment}-rds-monitoring-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })
  
  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  count      = var.environment == "production" ? 1 : 0
  role       = aws_iam_role.rds_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# ==================== READ REPLICA (Optional) ====================
resource "aws_db_instance" "read_replica" {
  count = var.create_read_replica ? 1 : 0
  
  identifier          = "${var.environment}-trustcheck-db-replica"
  replicate_source_db = aws_db_instance.postgres.identifier
  
  instance_class = var.db_instance_class
  
  skip_final_snapshot = true
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-trustcheck-db-replica"
      Type = "ReadReplica"
    }
  )
}