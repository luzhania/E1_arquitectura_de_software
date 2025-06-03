#!/bin/bash
set -e

echo "Application starting"
cd /home/ubuntu/

# Verify docker-compose.yml exists
if [ ! -f docker-compose.yml ]; then
    echo "❌ docker-compose.yml not found"
    exit 1
fi

# Start the application
echo "Starting containers..."
docker-compose --file docker-compose.yml up -d

if [ $? -ne 0 ]; then
    echo "❌ Failed to start containers"
    exit 1
fi

# Wait for containers to be ready
sleep 15

# Show running containers
echo "Running containers:"
docker-compose --file docker-compose.yml ps

echo "✅ Application started successfully"
