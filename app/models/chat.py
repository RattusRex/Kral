from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )

    username: Mapped[str] = mapped_column(
        String(50)
    )

    channel: Mapped[str] = mapped_column(
        String(20),
        default="general"
    )

    content: Mapped[str] = mapped_column(
        Text
    )

    formula = mapped_column(
        String(50),
        nullable=True
    )

    rolls = mapped_column(
        JSON,
        nullable=True
    )

    total = mapped_column(
        Integer,
        nullable=True
    )
