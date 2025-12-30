#!/bin/bash

echo "Starting Cender..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "ERROR: Docker is not running!"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo "Docker is running. Starting application..."
echo ""

# Create necessary directories
mkdir -p data credentials backend frontend

# Start Docker Compose
docker compose up --build