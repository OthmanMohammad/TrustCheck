output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.main.id
}

output "public_ip" {
  description = "EC2 public IP"
  value       = aws_instance.main.public_ip
}

output "private_ip" {
  description = "EC2 private IP"
  value       = aws_instance.main.private_ip
}

output "launch_template_id" {
  description = "Launch template ID"
  value       = aws_launch_template.main.id
}