#!/bin/bash
set -e

echo "Application starting"
cd /home/ubuntu/

# Verify docker-compose.yml exists
if [ ! -f docker-compose.yml ]; then
    echo "❌ docker-compose.yml not found"
    ls -la /home/ubuntu/
    exit 1
fi

if [ ! -f .env ]; then
    echo "❌ .env file not found"
    ls -la /home/ubuntu/
    exit 1
fi

echo "✅ Required files found"

# Ensure Docker is running
sudo systemctl start docker
sleep 2

# Create default network if needed
docker network create jobmaster-network 2>/dev/null || echo "Network already exists or not needed"

# Start the application
echo "Starting containers..."
docker-compose --file docker-compose.yml up -d

if [ $? -ne 0 ]; then
    echo "❌ Failed to start containers"
    docker-compose --file docker-compose.yml logs
    exit 1
fi

# Wait for containers to initialize
echo "Waiting for containers to initialize..."
sleep 30

# Show running containers
echo "Running containers:"
docker-compose --file docker-compose.yml ps

# Verify containers are running
EXPECTED_CONTAINERS=("api" "updates_broker" "requests_broker" "mongo_db")
for container in "${EXPECTED_CONTAINERS[@]}"; do
    if docker ps --format "table {{.Names}}" | grep -q "$container"; then
        echo "✅ Container $container is running"
    else
        echo "❌ Container $container is not running"
        docker-compose --file docker-compose.yml logs $container
        exit 1
    fi
done

echo "✅ Application started successfully"
