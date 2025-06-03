#!/bin/bash
set +e  # Don't exit on errors

echo "Stop Application"

# Simple approach: stop all containers without docker-compose
echo "Stopping all running containers..."

# Try with regular docker first
if docker ps -q &> /dev/null; then
    RUNNING_CONTAINERS=$(docker ps -q)
    if [ ! -z "$RUNNING_CONTAINERS" ]; then
        echo "Found running containers, stopping them..."
        docker stop $RUNNING_CONTAINERS || echo "Some containers failed to stop"
        docker rm $RUNNING_CONTAINERS || echo "Some containers failed to remove"
    else
        echo "No running containers found"
    fi
elif sudo docker ps -q &> /dev/null; then
    echo "Using sudo for Docker commands..."
    RUNNING_CONTAINERS=$(sudo docker ps -q)
    if [ ! -z "$RUNNING_CONTAINERS" ]; then
        echo "Found running containers, stopping them..."
        sudo docker stop $RUNNING_CONTAINERS || echo "Some containers failed to stop"
        sudo docker rm $RUNNING_CONTAINERS || echo "Some containers failed to remove"
    else
        echo "No running containers found"
    fi
else
    echo "Docker not accessible - skipping container cleanup"
fi

echo "✅ Application stop completed"
exit 0  # Always succeed