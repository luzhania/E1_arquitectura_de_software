#!/bin/bash
set +e  # Don't exit on errors

echo "Stop Application - Running as root"
cd /home/ubuntu/

# Ensure Docker daemon is running
sudo systemctl start docker || echo "Docker service start failed"

# Wait a moment for Docker to be ready
sleep 2

echo "Checking for running containers..."

# First, try to stop with docker-compose if file exists
if [ -f docker-compose.yml ]; then
    echo "Stopping with docker-compose..."
    docker-compose --file docker-compose.yml down --remove-orphans 2>/dev/null || echo "Docker-compose down failed (expected on first deployment)"
fi

# Get running containers with better error handling
echo "Checking for any remaining containers..."
RUNNING_CONTAINERS=$(docker ps -q 2>/dev/null | tr '\n' ' ')

if [ ! -z "$RUNNING_CONTAINERS" ] && [ "$RUNNING_CONTAINERS" != " " ]; then
    echo "Found running containers: $RUNNING_CONTAINERS"
    echo "Stopping containers..."
    for container in $RUNNING_CONTAINERS; do
        docker stop $container 2>/dev/null || echo "Failed to stop container $container"
        docker rm $container 2>/dev/null || echo "Failed to remove container $container"
    done
else
    echo "No running containers found"
fi

# Clean up any orphaned containers and networks
echo "Cleaning up resources..."
docker container prune -f 2>/dev/null || echo "Container prune failed"
docker network prune -f 2>/dev/null || echo "Network prune failed"

# Remove any existing networks that might conflict
docker network rm jobmaster-network 2>/dev/null || echo "jobmaster-network removal not needed"

echo "✅ Application stop completed"
exit 0  # Always succeed