variable "environment" {
  description = "Environment name"
  type        = string
}

variable "ec2_instance_id" {
  description = "EC2 instance ID to monitor"
  type        = string
}

variable "rds_instance_id" {
  description = "RDS instance ID to monitor"
  type        = string
}

variable "alb_arn" {
  description = "ALB ARN to monitor"
  type        = string
}

variable "alert_email" {
  description = "Email for alerts"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply"
  type        = map(string)
  default     = {}
}