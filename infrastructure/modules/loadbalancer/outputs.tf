output "alb_arn" {
  description = "ALB ARN"
  value       = aws_lb.main.arn
}

output "alb_dns" {
  description = "ALB DNS name"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "ALB zone ID"
  value       = aws_lb.main.zone_id
}

output "api_target_group_arn" {
  description = "API target group ARN"
  value       = aws_lb_target_group.api.arn
}

output "flower_target_group_arn" {
  description = "Flower target group ARN"
  value       = aws_lb_target_group.flower.arn
}