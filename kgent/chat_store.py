from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    desc,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "kgent_conversations"

    id: Mapped[str] = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = Column(String(255), nullable=False, default="New chat")
    repo_path: Mapped[str | None] = Column(String(1024), nullable=True)
    provider: Mapped[str | None] = Column(String(64), nullable=True)
    model: Mapped[str | None] = Column(String(128), nullable=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.position",
    )


class Message(Base):
    __tablename__ = "kgent_messages"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = Column(
        String(36), ForeignKey("kgent_conversations.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = Column(Integer, nullable=False)
    role: Mapped[str] = Column(String(16), nullable=False)
    content: Mapped[str] = Column(Text, nullable=False)
    context_json: Mapped[str | None] = Column(Text, nullable=True)
    provider: Mapped[str | None] = Column(String(64), nullable=True)
    model: Mapped[str | None] = Column(String(128), nullable=True)
    elapsed_ms: Mapped[int | None] = Column(Integer, nullable=True)
    created_at: Mapped[datetime] = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")


class ChatStore:
    def __init__(self, db_url: str | None = None):
        url = db_url or os.getenv("KGENT_DB_URL", "sqlite:///.kgent_store/chat.db")
        self.engine = create_engine(url, future=True)
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return Session(self.engine, future=True)

    def list_conversations(self, limit: int = 50) -> list[dict]:
        with self.session() as s:
            rows = (
                s.query(Conversation)
                .order_by(desc(Conversation.updated_at))
                .limit(limit)
                .all()
            )
            return [_conversation_summary(c) for c in rows]

    def get_conversation(self, conv_id: str) -> dict | None:
        with self.session() as s:
            conv = s.get(Conversation, conv_id)
            if not conv:
                return None
            return _conversation_full(conv)

    def create_conversation(
        self,
        title: str = "New chat",
        repo_path: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict:
        conv = Conversation(title=title, repo_path=repo_path, provider=provider, model=model)
        with self.session() as s:
            s.add(conv)
            s.commit()
            s.refresh(conv)
            return _conversation_summary(conv)

    def append_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        context_json: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        elapsed_ms: int | None = None,
    ) -> dict:
        with self.session() as s:
            conv = s.get(Conversation, conv_id)
            if not conv:
                raise ValueError(f"conversation not found: {conv_id}")
            position = len(conv.messages)
            msg = Message(
                conversation_id=conv_id,
                position=position,
                role=role,
                content=content,
                context_json=context_json,
                provider=provider,
                model=model,
                elapsed_ms=elapsed_ms,
            )
            s.add(msg)
            conv.updated_at = _utcnow()
            if conv.title == "New chat" and role == "user":
                conv.title = _summarize_title(content)
            s.commit()
            s.refresh(msg)
            return _message_to_dict(msg)

    def delete_conversation(self, conv_id: str) -> bool:
        with self.session() as s:
            conv = s.get(Conversation, conv_id)
            if not conv:
                return False
            s.delete(conv)
            s.commit()
            return True

    def update_conversation_meta(
        self,
        conv_id: str,
        provider: str | None = None,
        model: str | None = None,
        repo_path: str | None = None,
    ) -> bool:
        with self.session() as s:
            conv = s.get(Conversation, conv_id)
            if not conv:
                return False
            if provider is not None:
                conv.provider = provider
            if model is not None:
                conv.model = model
            if repo_path is not None:
                conv.repo_path = repo_path
            s.commit()
            return True


def _summarize_title(text: str, max_len: int = 60) -> str:
    one_line = text.strip().split("\n")[0]
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1].rstrip() + "..."


def _conversation_summary(c: Conversation) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "repo_path": c.repo_path,
        "provider": c.provider,
        "model": c.model,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def _conversation_full(c: Conversation) -> dict:
    return {
        **_conversation_summary(c),
        "messages": [_message_to_dict(m) for m in c.messages],
    }


def _message_to_dict(m: Message) -> dict:
    return {
        "id": m.id,
        "position": m.position,
        "role": m.role,
        "content": m.content,
        "context_json": m.context_json,
        "provider": m.provider,
        "model": m.model,
        "elapsed_ms": m.elapsed_ms,
        "created_at": m.created_at.isoformat(),
    }
