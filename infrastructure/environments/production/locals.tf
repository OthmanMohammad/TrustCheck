# Local Values and Computed Variables

locals {
  # Common tags for all resources
  common_tags = {
    Environment = var.environment
    Project     = "TrustCheck"
    ManagedBy   = "Terraform"
    Owner       = "DevOps"
    CostCenter  = var.environment == "production" ? "Production" : "Development"
    Backup      = var.environment == "production" ? "Required" : "Optional"
  }
  
  # Naming convention
  name_prefix = "trustcheck-${var.environment}"
  
  # Environment-specific settings
  is_production = var.environment == "production"
  
  # Cost optimization settings
  enable_monitoring = local.is_production
  enable_backups    = local.is_production
  enable_ha         = local.is_production
}