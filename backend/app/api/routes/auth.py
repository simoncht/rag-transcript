"""
Auth utilities and probes.

Provides a simple authenticated ping endpoint to quickly validate Clerk JWT
propagation through the API stack.
"""
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user
from app.models import User

router = APIRouter()


@router.get("/ping")
async def auth_ping(current_user: User = Depends(get_current_user)):
    """
    Auth-protected ping to verify JWT validity and user resolution.
    """
    return {
        "status": "ok",
        "user_id": str(current_user.id),
        "email": current_user.email,
    }
