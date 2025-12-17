"""
Authentication utilities for Clerk-backed JWT authentication.

Provides:
- ClerkJWTVerifier: verifies and decodes Clerk-issued JWTs using JWKS.
- get_current_user: FastAPI dependency that returns the current User.

Supports two modes controlled by settings.clerk_jwt_verification:
- Strict mode (True): full signature / issuer / audience verification.
- Relaxed mode (False): parse token without signature verification (dev only).
"""
from functools import lru_cache
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import get_db
from app.models import User


bearer_scheme = HTTPBearer(auto_error=False)


class ClerkJWTVerifier:
    """Verify Clerk-issued JWTs using JWKS."""

    def __init__(self) -> None:
        # Verification behaviour is controlled by settings.clerk_jwt_verification
        # and optional settings.clerk_issuer / settings.clerk_audience.
        pass

    @staticmethod
    @lru_cache(maxsize=4)
    def _get_jwks(issuer: str) -> Dict[str, Any]:
        """
        Fetch JWKS for the given issuer and cache the result.

        Args:
            issuer: Issuer URL from the JWT claims.

        Returns:
            JWKS payload as a dict.
        """
        if not issuer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing issuer",
            )

        jwks_url = issuer.rstrip("/") + "/.well-known/jwks.json"

        # In corporate development environments, HTTPS interception can break
        # standard certificate verification. The app already uses ssl_patch to
        # set PYTHONHTTPSVERIFY=0 in those cases. Respect that signal here for
        # JWKS fetching only in development.
        verify_ssl = True
        if settings.is_development and os.environ.get("PYTHONHTTPSVERIFY") == "0":
            verify_ssl = False

        try:
            with httpx.Client(timeout=5.0, verify=verify_ssl) as client:
                response = client.get(jwks_url)
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            detail = "Unable to fetch Clerk JWKS"
            if settings.debug:
                detail = f"{detail}: {exc}"
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=detail,
            ) from exc

        data = response.json()
        if "keys" not in data:
            detail = "Invalid JWKS payload from Clerk"
            if settings.debug:
                detail = f"{detail}: missing 'keys'"
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=detail,
            )
        return data

    @staticmethod
    def _get_signing_key(jwks: Dict[str, Any], kid: str) -> Dict[str, Any]:
        """
        Find signing key in JWKS for the given key ID.
        """
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signing key not found for token",
        )

    def verify_and_decode(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode a Clerk JWT.

        In strict mode (settings.clerk_jwt_verification=True), this validates:
        - Signature using Clerk JWKS (RS256).
        - Issuer (iss) – compared to settings.clerk_issuer if set, otherwise
          uses the issuer from the token.
        - Audience (aud) – if settings.clerk_audience is set.

        In relaxed mode, it parses claims without verifying the signature.

        Returns:
            Decoded claims as a dictionary.
        """
        try:
            unverified_header = jwt.get_unverified_header(token)
            unverified_claims = jwt.get_unverified_claims(token)
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization token",
            ) from exc

        # Relaxed mode: trust unverified claims (development only).
        if not settings.clerk_jwt_verification:
            return unverified_claims

        issuer = unverified_claims.get("iss")
        if settings.clerk_issuer:
            expected_issuer = settings.clerk_issuer
        else:
            expected_issuer = issuer

        if not issuer or not expected_issuer:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing issuer",
            )

        # Fetch JWKS and locate signing key
        jwks = self._get_jwks(issuer)
        kid = unverified_header.get("kid")
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing key id",
            )
        signing_key = self._get_signing_key(jwks, kid)

        # Configure audience verification
        verify_aud = settings.clerk_audience is not None
        decode_kwargs: Dict[str, Any] = {
            "algorithms": ["RS256"],
            "issuer": expected_issuer,
            "options": {"verify_aud": verify_aud},
        }
        if verify_aud:
            decode_kwargs["audience"] = settings.clerk_audience

        try:
            claims = jwt.decode(token, signing_key, **decode_kwargs)
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authorization token",
            ) from exc

        return claims


clerk_verifier = ClerkJWTVerifier()


def _extract_email(claims: Dict[str, Any]) -> Optional[str]:
    """
    Extract an email address from common Clerk JWT claim patterns.
    """
    email = claims.get("email")
    if email:
        return email

    # Clerk often provides an array of email addresses
    primary_email = claims.get("primary_email_address")
    if isinstance(primary_email, str):
        return primary_email

    email_addresses = claims.get("email_addresses")
    if isinstance(email_addresses, list) and email_addresses:
        first = email_addresses[0]
        if isinstance(first, dict):
            return first.get("email_address")
        if isinstance(first, str):
            return first

    return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Resolve the current authenticated user from a Clerk JWT.

    - Expects Authorization: Bearer <jwt> header.
    - Verifies and decodes the token via ClerkJWTVerifier.
    - Maps Clerk user (sub) to local User via clerk_user_id.
    - Lazily creates a User row on first login.
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
    claims = clerk_verifier.verify_and_decode(token)

    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
        )

    # Look up user by Clerk user ID
    user = db.query(User).filter(User.clerk_user_id == clerk_user_id).first()

    # Fallback: if no clerk_user_id match, try email link for legacy users
    if not user:
        email = _extract_email(claims)
        if email:
            user = db.query(User).filter(User.email == email).first()

    # Lazy-create user on first login
    if not user:
        email = _extract_email(claims) or f"{clerk_user_id}@example.invalid"
        user = User(
            clerk_user_id=clerk_user_id,
            email=email,
            full_name=claims.get("name"),
            subscription_tier="free",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user
