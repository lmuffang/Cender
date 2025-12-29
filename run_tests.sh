#!/bin/bash

# Script to run pytest tests
# Usage: ./run_tests.sh [options]

set -e

echo "🧪 Running backend tests..."

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose not found. Please install Docker Compose."
    exit 1
fi

# Run tests using docker-compose
docker-compose --profile testing run --rm --build pytest "$@"

echo "✅ Tests completed!"

