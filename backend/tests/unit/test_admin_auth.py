"""
Unit tests for admin authentication middleware.

Tests the get_admin_user dependency to ensure proper authorization.
"""
import pytest
from fastapi import HTTPException
from unittest.mock import Mock

from app.core.admin_auth import get_admin_user
from app.models import User


def test_admin_required_allows_superuser():
    """Superuser should pass admin check."""
    # Create a mock superuser
    mock_user = Mock(spec=User)
    mock_user.is_superuser = True
    mock_user.email = "admin@example.com"
    mock_user.id = "test-admin-id"

    # Should not raise an exception
    result = get_admin_user(current_user=mock_user)

    # Should return the same user
    assert result == mock_user
    assert result.is_superuser is True


def test_admin_required_blocks_regular_user():
    """Regular user should get 403."""
    # Create a mock regular user
    mock_user = Mock(spec=User)
    mock_user.is_superuser = False
    mock_user.email = "user@example.com"
    mock_user.id = "test-user-id"

    # Should raise 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        get_admin_user(current_user=mock_user)

    assert exc_info.value.status_code == 403
    assert "Admin access required" in exc_info.value.detail


def test_admin_check_with_none_superuser_flag():
    """User with is_superuser=None should be blocked."""
    # Create a mock user with None is_superuser
    mock_user = Mock(spec=User)
    mock_user.is_superuser = None
    mock_user.email = "user@example.com"

    # Should raise 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        get_admin_user(current_user=mock_user)

    assert exc_info.value.status_code == 403


def test_admin_check_preserves_user_attributes():
    """Admin check should preserve all user attributes."""
    # Create a mock superuser with various attributes
    mock_user = Mock(spec=User)
    mock_user.is_superuser = True
    mock_user.email = "admin@example.com"
    mock_user.full_name = "Admin User"
    mock_user.subscription_tier = "enterprise"
    mock_user.is_active = True

    result = get_admin_user(current_user=mock_user)

    # Verify all attributes are preserved
    assert result.email == "admin@example.com"
    assert result.full_name == "Admin User"
    assert result.subscription_tier == "enterprise"
    assert result.is_active is True
