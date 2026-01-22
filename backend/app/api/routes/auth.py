"""
Auth utilities and probes.

Provides a simple authenticated ping endpoint to quickly validate NextAuth JWT
propagation through the API stack.
"""
from fastapi import APIRouter, Depends, Request

from app.core.nextauth import get_current_user
from app.models import User
from app.core.rate_limit import limiter

router = APIRouter()


@router.get("/ping")
@limiter.limit("5/minute")
async def auth_ping(
    request: Request, current_user: User = Depends(get_current_user)
):
    """
    Auth-protected ping to verify JWT validity and user resolution.
    """
    return {
        "status": "ok",
        "user_id": str(current_user.id),
        "email": current_user.email,
    }


@router.get("/me")
@limiter.limit("5/minute")
async def auth_me(request: Request, current_user: User = Depends(get_current_user)):
    """
    Return the current authenticated user details for UI gating.
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_superuser": current_user.is_superuser,
        "oauth_provider": current_user.oauth_provider,
        "oauth_provider_id": current_user.oauth_provider_id,
    }
