variable "environment" {
  description = "Environment name"
  type        = string
}

variable "repository_name" {
  description = "ECR repository name"
  type        = string
}

variable "tags" {
  description = "Tags to apply"
  type        = map(string)
  default     = {}
}