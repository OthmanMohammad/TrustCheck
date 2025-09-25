#!/bin/bash
# Production-Ready EC2 Bootstrap Script
# This runs automatically on EVERY EC2 start/restart

set -e
exec > >(tee -a /var/log/user-data.log)
exec 2>&1

echo "========================================="
echo "Starting TrustCheck deployment at $(date)"
echo "========================================="

# ==================== SYSTEM SETUP ====================
yum update -y
yum install -y docker git amazon-cloudwatch-agent

# Start Docker
systemctl start docker
systemctl enable docker
usermod -a -G docker ec2-user

# Install Docker Compose
if [ ! -f /usr/local/bin/docker-compose ]; then
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# ==================== AWS CREDENTIALS ====================
# Use instance profile - no hardcoded credentials
export AWS_DEFAULT_REGION=${aws_region}

# ==================== APPLICATION DIRECTORY ====================
mkdir -p /opt/trustcheck
cd /opt/trustcheck

# ==================== ENVIRONMENT FILE ====================
cat > .env << 'EOF'
DATABASE_URL=postgresql://trustcheck_user:${db_password}@${db_host}/trustcheck
DB_HOST=${db_host}
DB_PORT=5432
DB_USER=trustcheck_user
DB_PASSWORD=${db_password}
DB_NAME=trustcheck

REDIS_URL=redis://${redis_host}:6379/0
REDIS_HOST=${redis_host}
REDIS_PORT=6379
REDIS_DB=0

CELERY_BROKER_URL=redis://${redis_host}:6379/0
CELERY_RESULT_BACKEND=redis://${redis_host}:6379/1

SECRET_KEY=${secret_key}
DEBUG=false
LOG_LEVEL=INFO
PROJECT_NAME=TrustCheck
ENVIRONMENT=production
VERSION=2.0.0

AWS_REGION=${aws_region}
AWS_DEFAULT_REGION=${aws_region}

OFAC_SDN_URL=https://www.treasury.gov/ofac/downloads/sdn.xml
UN_CONSOLIDATED_URL=https://scsanctions.un.org/resources/xml/en/consolidated.xml
EU_CONSOLIDATED_URL=https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/xmlFullSanctionsList/content
UK_HMT_URL=https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/1178224/UK_Sanctions_List.xlsx
EOF

# ==================== DOCKER COMPOSE ====================
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
      start_period: 40s
    logging:
      driver: awslogs
      options:
        awslogs-region: ${aws_region}
        awslogs-group: /aws/ec2/trustcheck
        awslogs-stream: web

  worker:
    image: ${ecr_uri}:latest
    container_name: trustcheck-worker
    restart: always
    env_file: .env
    command: ["celery", "-A", "src.celery_app.app", "worker", "--loglevel=info", "--concurrency=2"]
    logging:
      driver: awslogs
      options:
        awslogs-region: ${aws_region}
        awslogs-group: /aws/ec2/trustcheck
        awslogs-stream: worker

  beat:
    image: ${ecr_uri}:latest
    container_name: trustcheck-beat
    restart: always
    env_file: .env
    command: ["celery", "-A", "src.celery_app.app", "beat", "--loglevel=info"]
    logging:
      driver: awslogs
      options:
        awslogs-region: ${aws_region}
        awslogs-group: /aws/ec2/trustcheck
        awslogs-stream: beat

  flower:
    image: ${ecr_uri}:latest
    container_name: trustcheck-flower
    restart: always
    ports:
      - "5555:5555"
    env_file: .env
    command: ["celery", "-A", "src.celery_app.app", "flower", "--port=5555", "--basic_auth=admin:trustcheck2024"]
    logging:
      driver: awslogs
      options:
        awslogs-region: ${aws_region}
        awslogs-group: /aws/ec2/trustcheck
        awslogs-stream: flower
EOF

# ==================== STARTUP SCRIPT ====================
cat > /opt/trustcheck/startup.sh << 'SCRIPT'
#!/bin/bash
set -e

cd /opt/trustcheck

echo "Logging into ECR..."
aws ecr get-login-password --region ${aws_region} | docker login --username AWS --password-stdin ${ecr_uri}

echo "Pulling latest image..."
docker pull ${ecr_uri}:latest

echo "Running database migrations..."
docker run --rm --env-file .env ${ecr_uri}:latest alembic upgrade head || echo "Migration already applied"

echo "Starting services..."
docker-compose up -d

echo "Waiting for services to be healthy..."
sleep 30

# Initial data load if database is empty
ENTITY_COUNT=$(docker exec trustcheck-web python -c "
import asyncio
from src.infrastructure.database.connection import db_manager
from sqlalchemy import text
async def count():
    async with db_manager.get_session() as session:
        result = await session.execute(text('SELECT COUNT(*) FROM sanctioned_entities'))
        print(result.scalar())
asyncio.run(count())
" 2>/dev/null || echo "0")

if [ "$ENTITY_COUNT" -eq "0" ]; then
    echo "Database empty, triggering initial scrape..."
    docker exec trustcheck-worker python -c "
from src.tasks.scraping_tasks import scrape_all_sources_task
scrape_all_sources_task.delay()
print('Initial data scraping started')
    " || echo "Failed to start scraping"
fi

echo "Startup complete!"
SCRIPT

chmod +x /opt/trustcheck/startup.sh

# ==================== SYSTEMD SERVICE ====================
cat > /etc/systemd/system/trustcheck.service << 'EOF'
[Unit]
Description=TrustCheck Application
After=docker.service cloud-final.service
Requires=docker.service
StartLimitInterval=0

[Service]
Type=oneshot
RemainAfterExit=yes
Restart=on-failure
RestartSec=10
StartLimitInterval=0
WorkingDirectory=/opt/trustcheck
ExecStart=/opt/trustcheck/startup.sh
StandardOutput=append:/var/log/trustcheck.log
StandardError=append:/var/log/trustcheck.log

[Install]
WantedBy=multi-user.target
EOF

# ==================== HEALTH CHECK SCRIPT ====================
cat > /opt/trustcheck/health-check.sh << 'SCRIPT'
#!/bin/bash
HEALTH_STATUS=$(curl -s -o /dev/null -w "%%{http_code}" http://localhost:8000/health)

if [ "$HEALTH_STATUS" != "200" ]; then
    echo "$(date): Health check failed, restarting services..."
    cd /opt/trustcheck
    docker-compose restart
    
    # Send CloudWatch alarm
    aws cloudwatch put-metric-data \
        --namespace "TrustCheck" \
        --metric-name "HealthCheckFailed" \
        --value 1 \
        --region ${aws_region}
fi
SCRIPT

chmod +x /opt/trustcheck/health-check.sh

# ==================== CRON JOBS ====================
cat > /etc/cron.d/trustcheck << 'EOF'
# Health check every 5 minutes
*/5 * * * * root /opt/trustcheck/health-check.sh

# Daily update at 3 AM
0 3 * * * root cd /opt/trustcheck && docker pull ${ecr_uri}:latest && docker-compose up -d
EOF

# ==================== CLOUDWATCH AGENT ====================
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
          },
          {
            "file_path": "/var/log/trustcheck.log",
            "log_group_name": "/aws/ec2/trustcheck",
            "log_stream_name": "{instance_id}/application"
          }
        ]
      }
    }
  },
  "metrics": {
    "namespace": "TrustCheck",
    "metrics_collected": {
      "cpu": {
        "measurement": [{"name": "cpu_usage_idle"}],
        "totalcpu": false
      },
      "disk": {
        "measurement": [{"name": "used_percent"}],
        "resources": ["*"]
      },
      "mem": {
        "measurement": [{"name": "mem_used_percent"}]
      }
    }
  }
}
EOF

/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json \
    -s

# ==================== START EVERYTHING ====================
systemctl daemon-reload
systemctl enable trustcheck
systemctl start trustcheck

echo "========================================="
echo "TrustCheck deployment completed at $(date)"
echo "========================================="