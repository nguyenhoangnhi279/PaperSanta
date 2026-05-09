import asyncio
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer
from supabase import create_client

from app.core.config import settings

security = HTTPBearer()


async def get_current_user(token: str = Depends(security)) -> dict:
    try:
        supabase = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
        user = await asyncio.to_thread(supabase.auth.get_user, token.credentials)
        return {
            "user_id": user.user.id,
            "email": user.user.email,
        }
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
