from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ImageMetadata(BaseModel):
    id: Optional[int] = None
    image_id: Optional[int] = None
    user_id: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = []
    colors: List[str] = []
    ai_processing_status: str = "pending"
    created_at: Optional[datetime] = None

class ImageResponse(BaseModel):
    id: int
    filename: str
    original_path: str
    thumbnail_path: str
    uploaded_at: datetime
    user_id: str
    metadata: Optional[ImageMetadata] = None

class SearchRequest(BaseModel):
    query: str
    page: Optional[int] = 1
    limit: Optional[int] = 20

class SimilarImageRequest(BaseModel):
    image_id: int
    limit: Optional[int] = 10

class ColorFilterRequest(BaseModel):
    color: str
    limit: Optional[int] = 20

class AIAnalysisResult(BaseModel):
    description: str
    tags: List[str]
    colors: List[str]

class SearchResponse(BaseModel):
    images: List[ImageResponse]
    total: int
    page: int
    limit: int
    has_more: bool
