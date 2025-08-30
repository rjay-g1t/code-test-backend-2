import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class SupabaseClient:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        anon_key = os.getenv("SUPABASE_ANON_KEY")
        service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        
        if not url or not anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")
        
        self.url = url
        self.anon_key = anon_key
        self.service_key = service_key
        
        # Regular client for auth verification
        self.client: Client = create_client(url, anon_key)
        
        # Service role client for bypassing RLS (when we manually enforce user_id)
        if service_key:
            self.service_client: Client = create_client(url, service_key)
        else:
            # Fallback to anon client if no service key
            self.service_client: Client = self.client
    
    def get_client(self) -> Client:
        """Get the regular anon client"""
        return self.client
    
    def get_service_client(self) -> Client:
        """Get the service role client that bypasses RLS"""
        return self.service_client
