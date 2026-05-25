"""
chat.py — ChatSession với messages + pdf_ids lưu dưới dạng JSONB
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChatSession(Base):
    """Workspace chat: messages + pdf_ids lưu JSONB"""
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True,
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    messages: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    pdf_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    history_char_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False,
    )

    def __repr__(self) -> str:
        return f"<ChatSession id={self.id} user_id={self.user_id}>"