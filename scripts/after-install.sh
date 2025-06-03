#!/bin/bash
set -e

echo "Pulling application images..."
cd /home/ubuntu/

# Verify .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found in /home/ubuntu/"
    ls -la /home/ubuntu/
    exit 1
fi

echo "✅ Environment variables loaded from .env"

# Check if docker-compose.yml exists
if [ ! -f docker-compose.yml ]; then
    echo "❌ docker-compose.yml not found in /home/ubuntu/"
    ls -la /home/ubuntu/
    exit 1
fi

# Login to ECR Public (must use us-east-1)
echo "Logging into ECR Public..."
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws

if [ $? -ne 0 ]; then
    echo "❌ Failed to login to ECR Public"
    exit 1
fi

# Pull latest images
echo "Pulling Docker images..."
docker-compose --file docker-compose.yml pull

if [ $? -ne 0 ]; then
    echo "❌ Failed to pull Docker images"
    exit 1
fi

echo "✅ Images pulled successfully"
