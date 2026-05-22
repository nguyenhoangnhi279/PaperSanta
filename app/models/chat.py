"""
chat.py — ORM model cho bảng chat_sessions và chat_messages (Smart Reader)
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.embedding import PDFChunk
from app.models.pdf_document import PDFDocument
# Bảng trung gian nối ChatSession <-> PDFDocument 
class SessionPDF(Base):
    """Bảng trung gian giúp ChatSession biết nó đang phân tích những PDF nào"""
    __tablename__ = "session_pdfs"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), primary_key=True)
    pdf_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pdf_documents.id", ondelete="CASCADE"), primary_key=True)


class MessageCitation(Base):
    """Lưu vết chính xác tin nhắn AI đã trích dẫn đoạn PDF nào (Data Integrity)"""
    __tablename__ = "message_citations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_messages.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pdf_chunks.id", ondelete="CASCADE"), index=True)
    
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    message: Mapped["ChatMessage"] = relationship("ChatMessage", back_populates="citations")
    chunk: Mapped["PDFChunk"] = relationship("PDFChunk") 


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False) # 'user' hoặc 'ai'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
    
    citations: Mapped[list["MessageCitation"]] = relationship("MessageCitation", back_populates="message", cascade="all, delete-orphan")


class ChatSession(Base):
    """Bảng quản lý các phiên hỏi đáp giữa người dùng và AI"""
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    related_pdfs: Mapped[list["PDFDocument"]] = relationship("PDFDocument", secondary="session_pdfs")

    def __repr__(self) -> str:
        return f"<ChatSession id={self.id} user_id={self.user_id}>"