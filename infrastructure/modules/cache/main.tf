# Cache Module - ElastiCache Redis

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.environment}-cache-subnet-group"
  subnet_ids = var.subnet_ids
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-cache-subnet-group"
    }
  )
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.environment}-redis"
  engine              = "redis"
  engine_version      = "7.0"
  node_type           = var.node_type
  num_cache_nodes     = var.num_cache_nodes
  parameter_group_name = "default.redis7"
  
  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [var.security_group_id]
  
  snapshot_retention_limit = var.environment == "production" ? 1 : 0
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-redis"
    }
  )
}