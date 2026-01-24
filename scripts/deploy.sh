#!/bin/bash
# TrustCheck Deployment Script for Fly.io
# Usage: ./scripts/deploy.sh

set -e

echo "=== TrustCheck Deployment ==="

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo "Error: flyctl is not installed."
    echo "Install it with: curl -L https://fly.io/install.sh | sh"
    exit 1
fi

# Check if logged in
if ! flyctl auth whoami &> /dev/null; then
    echo "Please login to Fly.io first:"
    flyctl auth login
fi

# Check if app exists, create if not
APP_NAME="trustcheck-sanctions"
if ! flyctl apps list | grep -q "$APP_NAME"; then
    echo "Creating new Fly.io app: $APP_NAME"
    flyctl apps create "$APP_NAME"

    # Create volume for SQLite database
    echo "Creating persistent volume..."
    flyctl volumes create trustcheck_data --region iad --size 1 --app "$APP_NAME"
fi

# Deploy the application
echo "Deploying application..."
flyctl deploy --app "$APP_NAME"

# Show deployment status
echo ""
echo "=== Deployment Complete ==="
flyctl status --app "$APP_NAME"

echo ""
echo "Application URL: https://$APP_NAME.fly.dev"
echo "Health check: https://$APP_NAME.fly.dev/health"
echo "API docs: https://$APP_NAME.fly.dev/docs"
