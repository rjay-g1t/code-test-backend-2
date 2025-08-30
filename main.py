from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import asyncio
import aiofiles
import os
import uuid
from typing import List, Optional
from PIL import Image
import io
import json
from datetime import datetime, timezone
import logging
from dotenv import load_dotenv

from services.supabase_client import SupabaseClient
from services.ai_service import AIService
from models.schemas import (
    ImageResponse, ImageMetadata, SearchRequest, SimilarImageRequest, 
    ColorFilterRequest, SearchResponse, AIAnalysisResult
)
from utils.image_utils import create_thumbnail, create_thumbnail_bytes, extract_colors
from utils.auth import verify_token

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Image Gallery API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Initialize services
supabase_client = SupabaseClient()
ai_service = AIService()

# Create upload directory
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_DIR, "thumbnails"), exist_ok=True)

# Mount static files
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

@app.get("/")
async def root():
    return {"message": "AI Image Gallery API"}

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/upload", response_model=List[ImageResponse])
async def upload_images(
    files: List[UploadFile] = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Upload multiple images"""
    try:
        # Verify user authentication
        user_id = await verify_token(credentials.credentials, supabase_client)
        
        # Use service client for database operations (bypasses RLS since we manually enforce user_id)
        service_client = supabase_client.get_service_client()
        
        uploaded_images = []
        
        for file in files:
            # Validate file type
            if not file.content_type or not file.content_type.startswith('image/'):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not an image")
            
            # Read file content
            content = await file.read()
            
            # Generate unique filename
            file_extension = os.path.splitext(file.filename)[1]
            unique_filename = str(uuid.uuid4()) + file_extension
            
            # Upload to Supabase Storage
            try:
                # Upload original image to storage bucket
                storage_path = f"images/{unique_filename}"
                storage_result = service_client.storage.from_("images").upload(
                    storage_path, 
                    content,
                    file_options={"content-type": file.content_type}
                )
                
                # Create thumbnail and upload
                thumbnail_content = await create_thumbnail_bytes(content)
                thumbnail_filename = "thumb_" + unique_filename
                thumbnail_path = f"thumbnails/{thumbnail_filename}"
                
                service_client.storage.from_("images").upload(
                    thumbnail_path,
                    thumbnail_content,
                    file_options={"content-type": file.content_type}
                )
                
                # ALSO save files locally for AI processing and fallback serving
                local_image_path = os.path.join(UPLOAD_DIR, unique_filename)
                local_thumbnail_path = os.path.join(UPLOAD_DIR, "thumbnails", thumbnail_filename)
                
                # Save original locally
                with open(local_image_path, "wb") as f:
                    f.write(content)
                
                # Save thumbnail locally
                with open(local_thumbnail_path, "wb") as f:
                    f.write(thumbnail_content)
                
                # Use local paths for the API responses (faster serving)
                original_url = f"/uploads/{unique_filename}"
                thumbnail_url = f"/uploads/thumbnails/{thumbnail_filename}"
                
            except Exception as storage_error:
                logger.error(f"Storage upload error: {storage_error}")
                raise HTTPException(status_code=500, detail=f"Failed to upload to storage: {str(storage_error)}")
            
            # Save to database using service client with explicit user_id
            image_data = {
                "user_id": user_id,  # Manually enforce user ownership
                "filename": file.filename,
                "original_path": original_url,
                "thumbnail_path": thumbnail_url,
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            }
            
            result = service_client.table("images").insert(image_data).execute()
            image_id = result.data[0]["id"]
            
            # Start AI processing in background with the local file path
            local_file_path = os.path.join(UPLOAD_DIR, unique_filename)
            asyncio.create_task(process_image_ai(image_id, local_file_path, user_id))
            
            uploaded_images.append(ImageResponse(
                id=image_id,
                filename=file.filename,
                original_path=image_data["original_path"],
                thumbnail_path=image_data["thumbnail_path"],
                uploaded_at=image_data["uploaded_at"],
                user_id=user_id,  # Added missing user_id field
                metadata=None  # Will be populated after AI processing
            ))
        
        return uploaded_images
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_image_ai(image_id: int, local_image_path: str, user_id: str):
    """Process image with AI services in background"""
    try:
        logger.info(f"Starting AI processing for image {image_id}")
        
        # Use the local file directly for AI analysis
        if not os.path.exists(local_image_path):
            raise Exception(f"Local image file not found: {local_image_path}")
        
        # Analyze with AI
        ai_result = await ai_service.analyze_image(local_image_path)
        
        # Extract colors from the image
        image_colors = await extract_colors(local_image_path)
        
        # Save metadata to database
        metadata = {
            "image_id": image_id,
            "user_id": user_id,
            "description": ai_result.get("description", "An image"),
            "tags": ai_result.get("tags", []),
            "colors": image_colors,
            "ai_processing_status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        supabase_client.get_service_client().table("image_metadata").insert(metadata).execute()
        logger.info(f"AI processing completed for image {image_id}")
        
    except Exception as e:
        logger.error(f"AI processing error for image {image_id}: {str(e)}")
        # Save error status
        error_metadata = {
            "image_id": image_id,
            "user_id": user_id,
            "description": "AI processing failed",
            "tags": [],
            "colors": [],
            "ai_processing_status": "failed",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        supabase_client.get_service_client().table("image_metadata").insert(error_metadata).execute()

@app.get("/api/images", response_model=List[ImageResponse])
async def get_images(
    page: int = 1,
    limit: int = 20,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user's images with pagination"""
    try:
        user_id = await verify_token(credentials.credentials, supabase_client)
        
        # Use service client and manually filter by user_id
        service_client = supabase_client.get_service_client()
        
        offset = (page - 1) * limit
        
        # Get images with metadata, manually filtering by user_id
        query = service_client.table("images").select(
            "*, image_metadata(*)"
        ).eq("user_id", user_id).order("uploaded_at", desc=True).range(offset, offset + limit - 1)
        
        result = query.execute()
        
        images = []
        for img in result.data:
            metadata = None
            if img.get("image_metadata") and len(img["image_metadata"]) > 0:
                meta = img["image_metadata"][0]
                metadata = ImageMetadata(
                    description=meta.get("description"),
                    tags=meta.get("tags", []),
                    colors=meta.get("colors", []),
                    ai_processing_status=meta.get("ai_processing_status", "pending")
                )
            
            images.append(ImageResponse(
                id=img["id"],
                filename=img["filename"],
                original_path=img["original_path"],
                thumbnail_path=img["thumbnail_path"],
                uploaded_at=img["uploaded_at"],
                user_id=img["user_id"],  # Added missing user_id field
                metadata=metadata
            ))
        
        return images
        
    except Exception as e:
        logger.error(f"Get images error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search", response_model=List[ImageResponse])
async def search_images(
    search_request: SearchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Search images by text or tags"""
    try:
        user_id = await verify_token(credentials.credentials, supabase_client)
        
        query = search_request.query.lower()
        
        # Search in description and tags
        result = supabase_client.client.table("images").select(
            "*, image_metadata(*)"
        ).eq("user_id", user_id).execute()
        
        filtered_images = []
        for img in result.data:
            if img.get("image_metadata") and len(img["image_metadata"]) > 0:
                meta = img["image_metadata"][0]
                description = meta.get("description", "").lower()
                tags = [tag.lower() for tag in meta.get("tags", [])]
                
                # Check if query matches description or any tag
                if query in description or any(query in tag for tag in tags):
                    metadata = ImageMetadata(
                        description=meta.get("description"),
                        tags=meta.get("tags", []),
                        colors=meta.get("colors", []),
                        ai_processing_status=meta.get("ai_processing_status", "pending")
                    )
                    
                    filtered_images.append(ImageResponse(
                        id=img["id"],
                        filename=img["filename"],
                        original_path=img["original_path"],
                        thumbnail_path=img["thumbnail_path"],
                        uploaded_at=img["uploaded_at"],
                        metadata=metadata
                    ))
        
        return filtered_images
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/similar", response_model=List[ImageResponse])
async def find_similar_images(
    similar_request: SimilarImageRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Find similar images based on tags and colors"""
    try:
        user_id = await verify_token(credentials.credentials, supabase_client)
        
        # Get the reference image metadata
        ref_result = supabase_client.client.table("image_metadata").select("*").eq(
            "image_id", similar_request.image_id
        ).eq("user_id", user_id).execute()
        
        if not ref_result.data:
            raise HTTPException(status_code=404, detail="Reference image not found")
        
        ref_meta = ref_result.data[0]
        ref_tags = set(ref_meta.get("tags", []))
        ref_colors = set(ref_meta.get("colors", []))
        
        # Get all user's images with metadata
        all_images = supabase_client.client.table("images").select(
            "*, image_metadata(*)"
        ).eq("user_id", user_id).neq("id", similar_request.image_id).execute()
        
        similar_images = []
        for img in all_images.data:
            if img.get("image_metadata") and len(img["image_metadata"]) > 0:
                meta = img["image_metadata"][0]
                img_tags = set(meta.get("tags", []))
                img_colors = set(meta.get("colors", []))
                
                # Calculate similarity score
                tag_overlap = len(ref_tags.intersection(img_tags))
                color_overlap = len(ref_colors.intersection(img_colors))
                similarity_score = tag_overlap * 2 + color_overlap  # Weight tags more
                
                if similarity_score > 0:
                    metadata = ImageMetadata(
                        description=meta.get("description"),
                        tags=meta.get("tags", []),
                        colors=meta.get("colors", []),
                        ai_processing_status=meta.get("ai_processing_status", "pending")
                    )
                    
                    similar_images.append((similarity_score, ImageResponse(
                        id=img["id"],
                        filename=img["filename"],
                        original_path=img["original_path"],
                        thumbnail_path=img["thumbnail_path"],
                        uploaded_at=img["uploaded_at"],
                        metadata=metadata
                    )))
        
        # Sort by similarity score and return top results
        similar_images.sort(key=lambda x: x[0], reverse=True)
        return [img[1] for img in similar_images[:10]]
        
    except Exception as e:
        logger.error(f"Similar images error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/filter/color", response_model=List[ImageResponse])
async def filter_by_color(
    color: str = Form(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Filter images by dominant color"""
    try:
        user_id = await verify_token(credentials.credentials, supabase_client)
        
        # Get all user's images with the specified color
        result = supabase_client.client.table("images").select(
            "*, image_metadata(*)"
        ).eq("user_id", user_id).execute()
        
        filtered_images = []
        for img in result.data:
            if img.get("image_metadata") and len(img["image_metadata"]) > 0:
                meta = img["image_metadata"][0]
                colors = meta.get("colors", [])
                
                if color.lower() in [c.lower() for c in colors]:
                    metadata = ImageMetadata(
                        description=meta.get("description"),
                        tags=meta.get("tags", []),
                        colors=meta.get("colors", []),
                        ai_processing_status=meta.get("ai_processing_status", "pending")
                    )
                    
                    filtered_images.append(ImageResponse(
                        id=img["id"],
                        filename=img["filename"],
                        original_path=img["original_path"],
                        thumbnail_path=img["thumbnail_path"],
                        uploaded_at=img["uploaded_at"],
                        metadata=metadata
                    ))
        
        return filtered_images
        
    except Exception as e:
        logger.error(f"Color filter error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search", response_model=SearchResponse)
async def search_images(
    request: SearchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Search images by text query"""
    try:
        user_id = await verify_token(credentials.credentials, supabase_client)
        
        # Use service client and manually filter by user_id
        service_client = supabase_client.get_service_client()
        
        # Get all user's images with metadata
        result = service_client.table("images").select(
            "*, image_metadata(*)"
        ).eq("user_id", user_id).order("uploaded_at", desc=True).execute()
        
        search_results = []
        search_term_lower = request.query.lower()
        
        for img in result.data:
            # Check if image has metadata
            if img.get("image_metadata") and len(img["image_metadata"]) > 0:
                metadata = img["image_metadata"][0]
                description = metadata.get("description", "").lower()
                tags = [tag.lower() for tag in metadata.get("tags", [])]
                
                # Check if search term matches description or any tag
                if (search_term_lower in description or 
                    any(search_term_lower in tag for tag in tags)):
                    
                    image_metadata = ImageMetadata(
                        id=metadata.get("id"),
                        image_id=img["id"],
                        user_id=user_id,
                        description=metadata.get("description"),
                        tags=metadata.get("tags", []),
                        colors=metadata.get("colors", []),
                        ai_processing_status=metadata.get("ai_processing_status", "completed")
                    )
                    
                    search_results.append(ImageResponse(
                        id=img["id"],
                        filename=img["filename"],
                        original_path=img["original_path"],
                        thumbnail_path=img["thumbnail_path"],
                        uploaded_at=img["uploaded_at"],
                        user_id=user_id,
                        metadata=image_metadata
                    ))
        
        # Apply pagination
        total = len(search_results)
        start_idx = (request.page - 1) * request.limit
        end_idx = start_idx + request.limit
        paginated_results = search_results[start_idx:end_idx]
        
        has_more = end_idx < total
        
        return SearchResponse(
            images=paginated_results,
            total=total,
            page=request.page,
            limit=request.limit,
            has_more=has_more
        )
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/similar", response_model=List[ImageResponse])
async def find_similar_images(
    request: SimilarImageRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Find similar images based on tags and colors"""
    try:
        user_id = await verify_token(credentials.credentials, supabase_client)
        
        # Get the source image metadata
        source_response = supabase_client.table("image_metadata").select("*").eq("image_id", request.image_id).eq("user_id", user_id).execute()
        
        if not source_response.data:
            raise HTTPException(status_code=404, detail="Image not found")
        
        source_metadata = source_response.data[0]
        source_tags = source_metadata.get("tags", [])
        source_colors = source_metadata.get("colors", [])
        
        # Find similar images based on overlapping tags and colors
        similar_response = supabase_client.table("images").select("""
            id, filename, original_path, thumbnail_path, uploaded_at,
            image_metadata (
                id, description, tags, colors, ai_processing_status
            )
        """).eq("user_id", user_id).neq("id", request.image_id).execute()
        
        similar_images = []
        for img in similar_response.data:
            if img.get("image_metadata"):
                metadata = img["image_metadata"][0]
                img_tags = metadata.get("tags", [])
                img_colors = metadata.get("colors", [])
                
                # Calculate similarity score based on overlapping tags and colors
                tag_overlap = len(set(source_tags) & set(img_tags))
                color_overlap = len(set(source_colors) & set(img_colors))
                similarity_score = tag_overlap * 2 + color_overlap  # Weight tags more heavily
                
                if similarity_score > 0:
                    similar_images.append({
                        "image": img,
                        "metadata": metadata,
                        "score": similarity_score
                    })
        
        # Sort by similarity score and limit results
        similar_images.sort(key=lambda x: x["score"], reverse=True)
        similar_images = similar_images[:request.limit]
        
        # Format response
        result = []
        for item in similar_images:
            img = item["image"]
            metadata = item["metadata"]
            
            result.append(ImageResponse(
                id=img["id"],
                filename=img["filename"],
                original_path=img["original_path"],
                thumbnail_path=img["thumbnail_path"],
                uploaded_at=img["uploaded_at"],
                user_id=user_id,
                metadata=ImageMetadata(
                    id=metadata.get("id"),
                    image_id=img["id"],
                    user_id=user_id,
                    description=metadata.get("description"),
                    tags=metadata.get("tags", []),
                    colors=metadata.get("colors", []),
                    ai_processing_status=metadata.get("ai_processing_status", "completed")
                )
            ))
        
        return result
        
    except Exception as e:
        logger.error(f"Similar images error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/filter-by-color", response_model=List[ImageResponse])
async def filter_by_color(
    request: ColorFilterRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Filter images by dominant color"""
    try:
        user_id = await verify_token(credentials.credentials, supabase_client)
        
        # Search for images with the specified color
        response = supabase_client.table("images").select("""
            id, filename, original_path, thumbnail_path, uploaded_at,
            image_metadata (
                id, description, tags, colors, ai_processing_status
            )
        """).eq("user_id", user_id).execute()
        
        filtered_images = []
        for img in response.data:
            if img.get("image_metadata"):
                metadata = img["image_metadata"][0]
                img_colors = metadata.get("colors", [])
                
                # Check if the requested color is in the image's dominant colors
                if request.color.lower() in [color.lower() for color in img_colors]:
                    filtered_images.append(ImageResponse(
                        id=img["id"],
                        filename=img["filename"],
                        original_path=img["original_path"],
                        thumbnail_path=img["thumbnail_path"],
                        uploaded_at=img["uploaded_at"],
                        user_id=user_id,
                        metadata=ImageMetadata(
                            id=metadata.get("id"),
                            image_id=img["id"],
                            user_id=user_id,
                            description=metadata.get("description"),
                            tags=metadata.get("tags", []),
                            colors=metadata.get("colors", []),
                            ai_processing_status=metadata.get("ai_processing_status", "completed")
                        )
                    ))
        
        return filtered_images[:request.limit]
        
    except Exception as e:
        logger.error(f"Color filter error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
