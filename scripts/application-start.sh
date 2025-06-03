#!/bin/bash

echo "Application starting"
cd /home/ubuntu/
docker-compose --file docker-compose.yml up -d
