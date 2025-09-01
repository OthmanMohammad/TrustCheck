output "endpoint" {
  description = "Redis endpoint"
  value       = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "port" {
  description = "Redis port"
  value       = 6379
}

output "cluster_id" {
  description = "Redis cluster ID"
  value       = aws_elasticache_cluster.redis.id
}