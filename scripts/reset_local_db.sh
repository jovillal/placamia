#!/bin/bash
set -e

echo "Stopping local database..."
docker compose -f infra/docker/docker-compose.yml down -v

echo "Starting fresh local database..."
docker compose -f infra/docker/docker-compose.yml up -d