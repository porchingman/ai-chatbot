from supabase import create_client, Client
from app.config import settings

def get_supabase() -> Client:
    """
    Supabase 클라이언트를 반환합니다.
    """
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
