"""
NextAuth.js JWT verification for FastAPI.

Verifies JWTs issued by NextAuth.js using the NEXTAUTH_SECRET.
"""
from typing import Any, Dict, Optional
from datetime import datetime

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def verify_nextauth_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a NextAuth.js JWT.

    NextAuth.js uses HS256 (symmetric) signing with NEXTAUTH_SECRET.
    Token structure:
    {
      "sub": "google_provider_id",
      "email": "user@example.com",
      "name": "User Name",
      "picture": "https://...",
      "iat": 1234567890,
      "exp": 1234567890
    }
    """
    if not settings.nextauth_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="NextAuth secret not configured",
        )

    try:
        claims = jwt.decode(
            token,
            settings.nextauth_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},  # NextAuth doesn't use aud by default
        )
        return claims
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authorization token",
        ) from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the current authenticated user from a NextAuth.js JWT.

    - Expects Authorization: Bearer <jwt> header
    - Verifies and decodes the token
    - Maps OAuth provider ID to local User via oauth_provider_id
    - Lazily creates a User row on first login
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
        )

    token = credentials.credentials
    claims = verify_nextauth_token(token)

    oauth_provider_id = claims.get("sub")
    email = claims.get("email")

    if not oauth_provider_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing required claims",
        )

    # Look up user by email (primary identifier)
    user = db.query(User).filter(User.email == email).first()

    # Lazy-create user on first login
    if not user:
        user = User(
            oauth_provider="google",  # Hardcoded for now, extend later for multiple providers
            oauth_provider_id=oauth_provider_id,
            email=email,
            full_name=claims.get("name"),
            subscription_tier="free",
            is_active=True,
        )
        # Elevate to admin if email is in ADMIN_EMAILS
        if email in settings.admin_emails:
            user.is_superuser = True

        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update oauth_provider_id and full_name if changed
        user.oauth_provider_id = oauth_provider_id
        if claims.get("name"):
            user.full_name = claims.get("name")

        # Ensure admin emails stay elevated
        if email in settings.admin_emails and not user.is_superuser:
            user.is_superuser = True

        # Update last login
        user.last_login_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user
