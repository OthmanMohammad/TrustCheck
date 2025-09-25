resource "aws_autoscaling_group" "main" {
  name                = "${var.environment}-trustcheck-asg"
  vpc_zone_identifier = var.subnet_ids
  
  min_size         = 1
  max_size         = 3
  desired_capacity = 1
  
  health_check_type         = "ELB"
  health_check_grace_period = 300
  
  launch_template {
    id      = aws_launch_template.main.id
    version = "$Latest"
  }
  
  tag {
    key                 = "Name"
    value               = "${var.environment}-trustcheck-app"
    propagate_at_launch = true
  }
}

resource "aws_autoscaling_policy" "scale_up" {
  name                   = "${var.environment}-scale-up"
  scaling_adjustment     = 1
  adjustment_type        = "ChangeInCapacity"
  cooldown              = 300
  autoscaling_group_name = aws_autoscaling_group.main.name
}

resource "aws_cloudwatch_metric_alarm" "high_cpu" {
  alarm_name          = "${var.environment}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name        = "CPUUtilization"
  namespace          = "AWS/EC2"
  period             = "120"
  statistic          = "Average"
  threshold          = "80"
  alarm_description  = "This metric monitors ec2 cpu utilization"
  alarm_actions      = [aws_autoscaling_policy.scale_up.arn]
}