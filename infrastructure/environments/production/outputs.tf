# Production Environment Outputs

output "application_urls" {
  description = "Application endpoints"
  value = {
    api     = "http://${module.loadbalancer.alb_dns}"
    docs    = "http://${module.loadbalancer.alb_dns}/docs"
    health  = "http://${module.loadbalancer.alb_dns}/health"
    flower  = "http://${module.loadbalancer.alb_dns}:5555"
  }
}

output "infrastructure" {
  description = "Infrastructure details"
  value = {
    alb_dns       = module.loadbalancer.alb_dns
    ec2_public_ip = module.compute.public_ip
    rds_endpoint  = module.database.endpoint
    redis_endpoint = module.cache.endpoint
    ecr_uri       = module.ecr.repository_url
  }
  sensitive = true
}

output "ssh_command" {
  description = "SSH connection command"
  value       = "ssh -i ~/.ssh/${var.key_name}.pem ec2-user@${module.compute.public_ip}"
}

output "deployment_info" {
  description = "Deployment information"
  value = {
    environment = var.environment
    region      = var.aws_region
    vpc_id      = module.networking.vpc_id
  }
}