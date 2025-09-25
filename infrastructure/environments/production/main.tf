# Environment Configuration
# This is the entry point for production deployment

terraform {
  required_version = ">= 1.5"
  
  # Uncomment for remote state (recommended for production)
  # backend "s3" {
  #   bucket         = "trustcheck-terraform-state"
  #   key            = "production/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "trustcheck-terraform-locks"
  # }
}


# ==================== MODULES ====================

module "networking" {
  source = "../../modules/networking"
  
  environment         = var.environment
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  
  tags = local.common_tags
}

module "security" {
  source = "../../modules/security"
  
  environment = var.environment
  vpc_id      = module.networking.vpc_id
  
  tags = local.common_tags
}

module "database" {
  source = "../../modules/database"
  
  environment            = var.environment
  db_instance_class     = var.db_instance_class
  db_allocated_storage  = var.db_allocated_storage
  db_password           = var.db_password
  subnet_ids            = module.networking.private_subnet_ids
  security_group_id     = module.security.rds_security_group_id
  
  backup_retention_period = var.environment == "production" ? 7 : 1
  deletion_protection     = var.environment == "production" ? true : false
  
  tags = local.common_tags
}

module "cache" {
  source = "../../modules/cache"
  
  environment        = var.environment
  node_type         = var.redis_node_type
  num_cache_nodes   = var.redis_num_nodes
  subnet_ids        = module.networking.private_subnet_ids
  security_group_id = module.security.redis_security_group_id
  
  tags = local.common_tags
}

module "compute" {
  source = "../../modules/compute"
  
  environment         = var.environment
  instance_type      = var.ec2_instance_type
  key_name           = var.key_name
  subnet_id          = module.networking.public_subnet_ids[0]
  security_group_ids = [module.security.ec2_security_group_id]
  iam_instance_profile_name = module.security.ec2_instance_profile_name  # Add this line!
  
  # User data variables
  db_host     = module.database.endpoint
  db_password = var.db_password
  redis_host  = module.cache.endpoint
  secret_key  = var.secret_key
  ecr_uri     = module.ecr.repository_url
  aws_region  = var.aws_region
  
  tags = local.common_tags
}

module "loadbalancer" {
  source = "../../modules/loadbalancer"
  
  environment     = var.environment
  vpc_id          = module.networking.vpc_id
  subnet_ids      = module.networking.public_subnet_ids
  security_group_id = module.security.alb_security_group_id
  
  # Target configuration
  ec2_instance_id = module.compute.instance_id
  
  # Health check configuration
  health_check_path     = "/health"
  health_check_interval = 30
  
  tags = local.common_tags
}

module "ecr" {
  source = "../../modules/ecr"
  
  environment    = var.environment
  repository_name = "trustcheck"
  
  tags = local.common_tags
}

module "monitoring" {
  source = "../../modules/monitoring"
  
  environment = var.environment
  
  # Resources to monitor
  ec2_instance_id = module.compute.instance_id
  rds_instance_id = module.database.instance_id
  alb_arn        = module.loadbalancer.alb_arn
  
  # Alerting
  alert_email = var.alert_email
  
  tags = local.common_tags
}