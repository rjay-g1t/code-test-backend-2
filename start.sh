#!/bin/bash
# Railway startup script

set -e  # Exit on any error

echo "Starting AI Image Gallery Backend..."
echo "Environment: ${RAILWAY_ENVIRONMENT:-local}"
echo "Port: ${PORT:-8001}"

# Create uploads directory if it doesn't exist
mkdir -p uploads/thumbnails
echo "Created uploads directory structure"

# Check if required environment variables are set
if [ -z "$SUPABASE_URL" ]; then
    echo "Warning: SUPABASE_URL not set"
fi

if [ -z "$SUPABASE_ANON_KEY" ]; then
    echo "Warning: SUPABASE_ANON_KEY not set"
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "Warning: OPENAI_API_KEY not set"
fi

echo "Starting uvicorn server..."

# Start the application with production settings
if [ "$RAILWAY_ENVIRONMENT" = "production" ]; then
    echo "Running in production mode"
    exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001} --log-level info --access-log
else
    echo "Running in development mode"
    exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8001} --log-level info --reload
fi
