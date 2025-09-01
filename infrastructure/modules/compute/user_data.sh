#!/bin/bash
# EC2 User Data Script - TrustCheck Application Setup
# This script runs automatically when EC2 instance starts

set -e  # Exit on any error

# Log everything to file
exec > >(tee -a /var/log/user-data.log)
exec 2>&1
echo "========================================="
echo "Starting TrustCheck deployment at $(date)"
echo "========================================="

# ==================== SYSTEM UPDATES ====================
echo "📦 Updating system packages..."
yum update -y
yum install -y docker git htop jq

# ==================== DOCKER SETUP ====================
echo "🐳 Setting up Docker..."
service docker start
usermod -a -G docker ec2-user
systemctl enable docker

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose

# ==================== AWS CLI & ECR LOGIN ====================
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin ${ecr_uri}

# ==================== APPLICATION SETUP ====================
echo "📁 Setting up application directory..."
mkdir -p /opt/trustcheck
cd /opt/trustcheck

# Create production environment file
cat > .env << 'EOF'
# ==================== DATABASE ====================
DATABASE_URL=postgresql://trustcheck_user:${db_password}@${db_host}/trustcheck
DB_HOST=${db_host}
DB_PORT=5432
DB_USER=trustcheck_user
DB_PASSWORD=${db_password}
DB_NAME=trustcheck

# ==================== REDIS ====================
REDIS_URL=redis://${redis_host}:6379/0
REDIS_HOST=${redis_host}
REDIS_PORT=6379
REDIS_DB=0

# ==================== CELERY ====================
CELERY_BROKER_URL=redis://${redis_host}:6379/0
CELERY_RESULT_BACKEND=redis://${redis_host}:6379/1

# ==================== APPLICATION ====================
SECRET_KEY=${secret_key}
DEBUG=false
LOG_LEVEL=INFO
API_V1_STR=/api/v1
PROJECT_NAME=TrustCheck
ENVIRONMENT=production
VERSION=2.0.0

# ==================== CORS ====================
ALLOWED_ORIGINS=["*"]

# ==================== AWS ====================
AWS_REGION=${aws_region}
AWS_DEFAULT_REGION=${aws_region}

# ==================== SANCTIONS DATA SOURCES ====================
OFAC_SDN_URL=https://www.treasury.gov/ofac/downloads/sdn.xml
UN_CONSOLIDATED_URL=https://scsanctions.un.org/resources/xml/en/consolidated.xml
EU_CONSOLIDATED_URL=https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/xmlFullSanctionsList/content
UK_HMT_URL=https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/1178224/UK_Sanctions_List.xlsx
EOF

# Create docker-compose.yml for production
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  web:
    image: ${ecr_uri}:latest
    container_name: trustcheck-web
    restart: always
    ports:
      - "8000:8000"
    env_file: .env
    command: ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  worker:
    image: ${ecr_uri}:latest
    container_name: trustcheck-worker
    restart: always
    env_file: .env
    command: ["celery", "-A", "src.celery_app.app", "worker", "--loglevel=info", "--concurrency=2"]
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  beat:
    image: ${ecr_uri}:latest
    container_name: trustcheck-beat
    restart: always
    env_file: .env
    command: ["celery", "-A", "src.celery_app.app", "beat", "--loglevel=info"]
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  flower:
    image: ${ecr_uri}:latest
    container_name: trustcheck-flower
    restart: always
    ports:
      - "5555:5555"
    env_file: .env
    command: ["celery", "-A", "src.celery_app.app", "flower", "--port=5555", "--basic_auth=admin:trustcheck2024"]
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

# ==================== PULL AND START APPLICATION ====================
echo "🚀 Pulling Docker image..."
docker pull ${ecr_uri}:latest

echo "📊 Running database migrations..."
docker run --rm --env-file .env ${ecr_uri}:latest alembic upgrade head

echo "🎯 Starting application services..."
docker-compose up -d

# ==================== SETUP SYSTEMD SERVICE ====================
echo "⚙️ Setting up systemd service..."
cat > /etc/systemd/system/trustcheck.service << 'EOF'
[Unit]
Description=TrustCheck Application
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/trustcheck
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
ExecReload=/usr/local/bin/docker-compose restart
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable trustcheck

# ==================== SETUP CLOUDWATCH AGENT ====================
echo "📊 Setting up CloudWatch monitoring..."
wget https://s3.amazonaws.com/amazoncloudwatch-agent/amazon_linux/amd64/latest/amazon-cloudwatch-agent.rpm
rpm -U ./amazon-cloudwatch-agent.rpm

# Configure CloudWatch agent
cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << 'EOF'
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/user-data.log",
            "log_group_name": "/aws/ec2/trustcheck",
            "log_stream_name": "{instance_id}/user-data"
          }
        ]
      }
    }
  },
  "metrics": {
    "namespace": "TrustCheck",
    "metrics_collected": {
      "mem": {
        "measurement": [
          {
            "name": "mem_used_percent",
            "rename": "MemoryUtilization"
          }
        ]
      },
      "disk": {
        "measurement": [
          {
            "name": "used_percent",
            "rename": "DiskUtilization",
            "resources": [
              "*"
            ]
          }
        ]
      }
    }
  }
}
EOF

/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config \
  -m ec2 \
  -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json

# ==================== SETUP AUTO-UPDATE SCRIPT ====================
echo "🔄 Setting up auto-update script..."
cat > /opt/trustcheck/update.sh << 'SCRIPT_EOF'
#!/bin/bash
# Script to update application from ECR

set -e
cd /opt/trustcheck

echo "Pulling latest image..."
aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin ${ecr_uri}
docker pull ${ecr_uri}:latest

echo "Running migrations..."
docker run --rm --env-file .env ${ecr_uri}:latest alembic upgrade head

echo "Restarting services..."
docker-compose down
docker-compose up -d

echo "Update completed at $(date)"
SCRIPT_EOF

chmod +x /opt/trustcheck/update.sh

# ==================== SETUP CRON FOR HEALTH CHECKS ====================
echo "⏰ Setting up health check cron..."
cat > /opt/trustcheck/health-check.sh << 'SCRIPT_EOF'
#!/bin/bash
# Health check script

HEALTH_STATUS=$(curl -s -o /dev/null -w "%%{http_code}" http://localhost:8000/health)

if [ "$HEALTH_STATUS" != "200" ]; then
    echo "Health check failed at $(date). Restarting services..."
    cd /opt/trustcheck
    docker-compose restart
fi
SCRIPT_EOF

chmod +x /opt/trustcheck/health-check.sh

# Add to crontab
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/trustcheck/health-check.sh") | crontab -

# ==================== FINAL CHECKS ====================
echo "✅ Waiting for services to be ready..."
sleep 30

# Check if services are running
docker ps

# Test API endpoint
curl -f http://localhost:8000/health || echo "⚠️ API not yet ready"

echo "========================================="
echo "✅ TrustCheck deployment completed at $(date)"
echo "========================================="
echo "Services running:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"