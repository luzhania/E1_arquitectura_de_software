#!/bin/bash

echo "Stop Application"
cd /home/ubuntu/
docker compose --file docker-compose.yml down