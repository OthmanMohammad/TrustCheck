# Monitoring Module - CloudWatch

resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/ec2/${var.environment}-trustcheck"
  retention_in_days = var.environment == "production" ? 7 : 3
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-app-logs"
    }
  )
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.environment}-trustcheck-dashboard"
  
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/EC2", "CPUUtilization", { stat = "Average" }],
            ["AWS/ApplicationELB", "TargetResponseTime", { stat = "Average" }],
            ["AWS/RDS", "DatabaseConnections", { stat = "Average" }]
          ]
          period = 300
          stat   = "Average"
          region = "us-east-1"
          title  = "System Metrics"
        }
      }
    ]
  })
}

# SNS Topic for Alerts
resource "aws_sns_topic" "alerts" {
  count = var.alert_email != "" ? 1 : 0
  name  = "${var.environment}-trustcheck-alerts"
  
  tags = var.tags
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts[0].arn
  protocol  = "email"
  endpoint  = var.alert_email
}