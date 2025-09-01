# Load Balancer Module

# ==================== APPLICATION LOAD BALANCER ====================
resource "aws_lb" "main" {
  name               = "${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.security_group_id]
  subnets           = var.subnet_ids
  
  enable_deletion_protection = var.environment == "production"
  enable_http2              = true
  enable_cross_zone_load_balancing = true
  
  access_logs {
    bucket  = var.access_logs_bucket
    prefix  = "alb"
    enabled = var.enable_access_logs
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-alb"
    }
  )
}

# ==================== TARGET GROUPS ====================

# API Target Group
resource "aws_lb_target_group" "api" {
  name     = "${var.environment}-api-tg"
  port     = 8000
  protocol = "HTTP"
  vpc_id   = var.vpc_id
  
  deregistration_delay = 30
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = var.health_check_interval
    path                = var.health_check_path
    matcher             = "200"
  }
  
  stickiness {
    type            = "lb_cookie"
    cookie_duration = 86400
    enabled         = true
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-api-tg"
    }
  )
}

# Flower Target Group
resource "aws_lb_target_group" "flower" {
  name     = "${var.environment}-flower-tg"
  port     = 5555
  protocol = "HTTP"
  vpc_id   = var.vpc_id
  
  deregistration_delay = 30
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/"
    matcher             = "200,401"  # 401 because Flower has basic auth
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-flower-tg"
    }
  )
}

# ==================== TARGET GROUP ATTACHMENTS ====================
resource "aws_lb_target_group_attachment" "api" {
  target_group_arn = aws_lb_target_group.api.arn
  target_id        = var.ec2_instance_id
  port             = 8000
}

resource "aws_lb_target_group_attachment" "flower" {
  target_group_arn = aws_lb_target_group.flower.arn
  target_id        = var.ec2_instance_id
  port             = 5555
}

# ==================== LISTENERS ====================

# HTTP Listener (Port 80)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# Flower Listener (Port 5555)
resource "aws_lb_listener" "flower" {
  load_balancer_arn = aws_lb.main.arn
  port              = "5555"
  protocol          = "HTTP"
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.flower.arn
  }
}

# HTTPS Listener (Port 443) - Ready for SSL
resource "aws_lb_listener" "https" {
  count = var.certificate_arn != "" ? 1 : 0
  
  load_balancer_arn = aws_lb.main.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS-1-2-2017-01"
  certificate_arn   = var.certificate_arn
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# ==================== LISTENER RULES ====================

# API Path Rules
resource "aws_lb_listener_rule" "api_v1" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 100
  
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  
  condition {
    path_pattern {
      values = ["/api/v1/*"]
    }
  }
}

resource "aws_lb_listener_rule" "api_v2" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 99
  
  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
  
  condition {
    path_pattern {
      values = ["/api/v2/*"]
    }
  }
}

# Redirect HTTP to HTTPS (when SSL is enabled)
resource "aws_lb_listener_rule" "redirect_to_https" {
  count = var.certificate_arn != "" ? 1 : 0
  
  listener_arn = aws_lb_listener.http.arn
  priority     = 1
  
  action {
    type = "redirect"
    
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
  
  condition {
    path_pattern {
      values = ["/*"]
    }
  }
}