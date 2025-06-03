#!/bin/bash
set +e  # Don't exit on errors

echo "Stop Application - Running as root"
cd /home/ubuntu/

# Since we're running as root, we can access Docker directly
echo "Checking for running containers..."

# Get running containers
RUNNING_CONTAINERS=$(docker ps -q 2>/dev/null || echo "")

if [ ! -z "$RUNNING_CONTAINERS" ]; then
    echo "Found running containers, stopping them..."
    docker stop $RUNNING_CONTAINERS || echo "Some containers failed to stop"
    docker rm $RUNNING_CONTAINERS || echo "Some containers failed to remove"
else
    echo "No running containers found"
fi

# Also try docker-compose if file exists
if [ -f docker-compose.yml ]; then
    echo "Stopping with docker-compose..."
    docker-compose --file docker-compose.yml down --remove-orphans || echo "Docker-compose down failed (expected on first deployment)"
fi

# Clean up any orphaned containers
docker container prune -f || echo "Container prune failed"

echo "✅ Application stop completed"
exit 0  # Always succeed