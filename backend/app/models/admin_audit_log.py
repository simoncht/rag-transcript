"""
Admin audit log for monitoring chat/message activity.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.db.base import Base


class AdminAuditLog(Base):
    """
    Append-only audit events so admins can review chat activity.
    """

    __tablename__ = "admin_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(50), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True)
    role = Column(String(20), nullable=True)
    content = Column(Text, nullable=True)
    token_count = Column(Integer, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    flags = Column(ARRAY(String), nullable=True)
    message_metadata = Column(JSONB, nullable=True)
    ip_hash = Column(String(128), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User")
    conversation = relationship("Conversation")
    message = relationship("Message")

    def __repr__(self):
        return (
            f"<AdminAuditLog(id={self.id}, event_type={self.event_type}, "
            f"user_id={self.user_id}, conversation_id={self.conversation_id})>"
        )

    @property
    def has_flags(self) -> bool:
        return bool(self.flags)
