# Compute Module - EC2 Instance with Auto-scaling Ready

# ==================== SSH KEY PAIR ====================
resource "aws_key_pair" "main" {
  key_name   = var.key_name
  public_key = file("${path.module}/keys/${var.key_name}.pub")
  
  tags = merge(
    var.tags,
    {
      Name = var.key_name
    }
  )
}

# ==================== LAUNCH TEMPLATE ====================
resource "aws_launch_template" "main" {
  name_prefix   = "${var.environment}-trustcheck-"
  image_id      = data.aws_ami.amazon_linux_2.id
  instance_type = var.instance_type
  
  key_name = aws_key_pair.main.key_name
  
  vpc_security_group_ids = var.security_group_ids
  
  iam_instance_profile {
    name = var.iam_instance_profile_name
  }
  
  block_device_mappings {
    device_name = "/dev/xvda"
    
    ebs {
      volume_type           = "gp3"
      volume_size           = var.root_volume_size
      iops                  = 3000
      throughput            = 125
      encrypted             = true
      delete_on_termination = true
    }
  }
  
  monitoring {
    enabled = var.enable_detailed_monitoring
  }
  
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                = "required"  # IMDSv2
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }
  
  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    environment  = var.environment
    db_host     = var.db_host
    db_password = var.db_password
    redis_host  = var.redis_host
    secret_key  = var.secret_key
    ecr_uri     = var.ecr_uri
    aws_region  = var.aws_region
  }))
  
  tag_specifications {
    resource_type = "instance"
    tags = merge(
      var.tags,
      {
        Name = "${var.environment}-trustcheck-app"
      }
    )
  }
  
  tag_specifications {
    resource_type = "volume"
    tags = merge(
      var.tags,
      {
        Name = "${var.environment}-trustcheck-volume"
      }
    )
  }
}

# ==================== EC2 INSTANCE ====================
resource "aws_instance" "main" {
  launch_template {
    id      = aws_launch_template.main.id
    version = "$Latest"
  }
  
  subnet_id = var.subnet_id
  
  # Ensure instance is replaced if launch template changes
  lifecycle {
    create_before_destroy = true
  }
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-trustcheck-app"
    }
  )
}

# ==================== ELASTIC IP ====================
resource "aws_eip" "main" {
  count    = var.associate_public_ip ? 1 : 0
  instance = aws_instance.main.id
  domain   = "vpc"
  
  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-trustcheck-eip"
    }
  )
}

# ==================== AUTO SCALING GROUP (Ready for future) ====================
resource "aws_autoscaling_group" "main" {
  count = var.enable_auto_scaling ? 1 : 0
  
  name                = "${var.environment}-trustcheck-asg"
  vpc_zone_identifier = var.asg_subnet_ids
  
  min_size         = var.asg_min_size
  max_size         = var.asg_max_size
  desired_capacity = var.asg_desired_capacity
  
  health_check_type         = "ELB"
  health_check_grace_period = 300
  
  launch_template {
    id      = aws_launch_template.main.id
    version = "$Latest"
  }
  
  tag {
    key                 = "Name"
    value               = "${var.environment}-trustcheck-asg-instance"
    propagate_at_launch = true
  }
  
  dynamic "tag" {
    for_each = var.tags
    content {
      key                 = tag.key
      value               = tag.value
      propagate_at_launch = true
    }
  }
}

# ==================== DATA SOURCES ====================
data "aws_ami" "amazon_linux_2" {
  most_recent = true
  owners      = ["amazon"]
  
  filter {
    name   = "name"
    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
  }
  
  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}