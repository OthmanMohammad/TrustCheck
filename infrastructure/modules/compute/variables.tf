variable "environment" {
  description = "Environment name"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.small"
}

variable "key_name" {
  description = "SSH key name"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for instance"
  type        = string
}

variable "security_group_ids" {
  description = "Security group IDs"
  type        = list(string)
}

variable "iam_instance_profile_name" {
  description = "IAM instance profile name"
  type        = string
  default     = ""
}

variable "root_volume_size" {
  description = "Root volume size in GB"
  type        = number
  default     = 20
}

variable "enable_detailed_monitoring" {
  description = "Enable detailed monitoring"
  type        = bool
  default     = false
}

variable "associate_public_ip" {
  description = "Associate public IP"
  type        = bool
  default     = true
}

variable "enable_auto_scaling" {
  description = "Enable auto scaling group"
  type        = bool
  default     = false
}

variable "asg_subnet_ids" {
  description = "Subnet IDs for auto scaling group"
  type        = list(string)
  default     = []
}

variable "asg_min_size" {
  description = "ASG minimum size"
  type        = number
  default     = 1
}

variable "asg_max_size" {
  description = "ASG maximum size"
  type        = number
  default     = 3
}

variable "asg_desired_capacity" {
  description = "ASG desired capacity"
  type        = number
  default     = 1
}

# User data variables
variable "db_host" {
  description = "Database host"
  type        = string
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "redis_host" {
  description = "Redis host"
  type        = string
}

variable "secret_key" {
  description = "Application secret key"
  type        = string
  sensitive   = true
}

variable "ecr_uri" {
  description = "ECR repository URI"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "tags" {
  description = "Tags to apply"
  type        = map(string)
  default     = {}
}