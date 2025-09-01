output "endpoint" {
  description = "Database endpoint"
  value       = aws_db_instance.postgres.address
}

output "port" {
  description = "Database port"
  value       = aws_db_instance.postgres.port
}

output "instance_id" {
  description = "Database instance ID"
  value       = aws_db_instance.postgres.id
}

output "database_name" {
  description = "Database name"
  value       = aws_db_instance.postgres.db_name
}