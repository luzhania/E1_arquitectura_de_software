#!/bin/bash

echo "Validating service"

# Wait for services to be ready
sleep 30

# Check if API is responding
if curl -f http://localhost:8000/ > /dev/null 2>&1; then
    echo "API service is running"
    exit 0
else
    echo "API service failed to start"
    # Show logs for debugging
    docker compose --file /home/ubuntu/docker-compose.yml logs api
    exit 1
fi