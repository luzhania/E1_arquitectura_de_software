#!/bin/bash

echo "Pulling application"
cd /home/ubuntu/

# Login to ECR Public (must use us-east-1)
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws

# Pull latest images
docker-compose --file docker-compose.yml pull
