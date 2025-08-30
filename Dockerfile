# Backend Dockerfile - Optimized for Railway
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Make start script executable
RUN chmod +x start.sh

# Create uploads directory with proper permissions
RUN mkdir -p uploads/thumbnails && chmod -R 755 uploads

# Expose port (Railway will assign the actual port)
EXPOSE $PORT

# Run the application using start script
CMD ["./start.sh"]
