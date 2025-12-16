"""
Admin authentication and authorization middleware.

Provides:
- get_admin_user: FastAPI dependency that ensures user is a superuser.
- Admin-only route protection.
"""
from fastapi import Depends, HTTPException, status

from app.core.auth import get_current_user
from app.models import User


def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Admin-only dependency that verifies the current user is a superuser.

    This dependency should be used on all admin-only routes to ensure
    that only users with is_superuser=True can access them.

    Args:
        current_user: The authenticated user from get_current_user dependency

    Returns:
        User: The current user if they are a superuser

    Raises:
        HTTPException: 403 Forbidden if user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required. Only superusers can access this resource.",
        )

    return current_user
