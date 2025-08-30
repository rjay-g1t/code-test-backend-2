# AI Image Gallery Backend

A FastAPI-based backend for an AI-powered image gallery application with Supabase integration and OpenAI image analysis.

## Features

- Image upload and management
- AI-powered image analysis using OpenAI Vision API
- Supabase database integration
- User authentication
- Image thumbnail generation
- Color extraction
- Search and filtering capabilities

## Environment Variables

Required environment variables (set these in Railway dashboard):

```env
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
OPENAI_API_KEY=your_openai_api_key_here
CORS_ORIGINS=https://your-frontend-domain.com,http://localhost:3000
UPLOAD_DIR=./uploads
```

## Railway Deployment

This application is optimized for Railway deployment:

1. **Connect Repository**: Link your GitHub repository to Railway
2. **Set Environment Variables**: Add all required environment variables in Railway dashboard
3. **Deploy**: Railway will automatically build and deploy using the Dockerfile

### Railway-specific features:
- Dynamic port configuration (uses Railway's `PORT` environment variable)
- Health check endpoint at `/health`
- Optimized Docker build with `.dockerignore`
- CORS configuration for production domains

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in your values

3. Run the server:
```bash
uvicorn main:app --reload --port 8001
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /api/upload` - Upload images
- `GET /api/images` - List images
- `POST /api/search` - Search images
- `POST /api/similar` - Find similar images
- `POST /api/filter/color` - Filter by color

## Docker

Build and run with Docker:

```bash
docker build -t ai-image-gallery-backend .
docker run -p 8001:8001 --env-file .env ai-image-gallery-backend
```
