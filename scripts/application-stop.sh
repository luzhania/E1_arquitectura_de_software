#!/bin/bash
set +e  # Don't exit on errors

echo "Stop Application"
cd /home/ubuntu/

# Check if docker-compose.yml exists
if [ -f docker-compose.yml ]; then
    echo "Stopping containers with docker-compose..."
    docker-compose --file docker-compose.yml down --remove-orphans || echo "No containers to stop or docker-compose failed"
else
    echo "No docker-compose.yml found, stopping any running containers..."
    # Stop all running containers (if any)
    RUNNING_CONTAINERS=$(docker ps -q)
    if [ ! -z "$RUNNING_CONTAINERS" ]; then
        echo "Stopping running containers..."
        docker stop $RUNNING_CONTAINERS || echo "Failed to stop some containers"
        docker rm $RUNNING_CONTAINERS || echo "Failed to remove some containers"
    else
        echo "No running containers found"
    fi
fi

echo "✅ Application stop completed"
exit 0  # Always succeed