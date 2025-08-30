from fastapi import HTTPException
from services.supabase_client import SupabaseClient
import jwt
import os

async def verify_token(token: str, supabase_client: SupabaseClient) -> str:
    """Verify JWT token and return user ID"""
    try:
        # Use Supabase client to verify the token
        response = supabase_client.client.auth.get_user(token)
        
        if response.user:
            return response.user.id
        else:
            raise HTTPException(status_code=401, detail="Invalid token")
        
    except Exception as e:
        print(f"Auth error: {e}")  # Debug log
        raise HTTPException(status_code=401, detail="Invalid or expired token")
