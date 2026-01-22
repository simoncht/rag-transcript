"""
Helpers for emitting admin audit events.
"""
import hashlib
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AdminAuditLog, Message


def _hash_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


def _extract_flags(metadata: Optional[dict]) -> List[str]:
    flags: List[str] = []
    if not isinstance(metadata, dict):
        return flags

    for key in ("flags", "moderation_flags", "safety_flags"):
        value = metadata.get(key)
        if isinstance(value, list):
            flags.extend(str(v) for v in value)
        elif isinstance(value, str):
            flags.append(value)

    if metadata.get("had_error"):
        flags.append("error")
    if metadata.get("pii_detected"):
        flags.append("pii_detected")

    return sorted(set(flags))


def log_chat_message(
    db: Session,
    *,
    request: Optional[Request],
    user_id: Optional[UUID],
    conversation_id: Optional[UUID],
    message: Message,
    event_type: str = "chat_message",
    extra_flags: Optional[Sequence[str]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
):
    """
    Persist a chat message event into the admin audit log.
    """
    ip_hash = _hash_ip(request.client.host if request and request.client else None)
    user_agent = request.headers.get("user-agent") if request else None

    flags = _extract_flags(message.message_metadata)
    if extra_flags:
        flags.extend(str(flag) for flag in extra_flags)
        flags = sorted(set(flags))

    metadata: Dict[str, Any] = {}
    if isinstance(message.message_metadata, dict):
        metadata.update(message.message_metadata)
    if extra_metadata:
        metadata.update(extra_metadata)

    log_entry = AdminAuditLog(
        event_type=event_type,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message.id,
        role=message.role,
        content=message.content,
        token_count=message.token_count,
        input_tokens=message.input_tokens,
        output_tokens=message.output_tokens,
        flags=flags or None,
        message_metadata=metadata or None,
        ip_hash=ip_hash,
        user_agent=user_agent,
    )
    db.add(log_entry)
