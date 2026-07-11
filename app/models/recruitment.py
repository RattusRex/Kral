from datetime import UTC, date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class GameRecruitment(Base):
    __tablename__ = "game_recruitments"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    real_date: Mapped[date] = mapped_column(Date)
    game_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    duration: Mapped[str] = mapped_column(String(100))
    location: Mapped[str] = mapped_column(String(300))
    quest: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        String(20), default="upcoming", server_default="upcoming"
    )

    author = relationship("User")
    applications = relationship(
        "GameApplication",
        back_populates="recruitment",
        cascade="all, delete-orphan",
        order_by="GameApplication.created_at",
    )
    messages = relationship(
        "RecruitmentMessage",
        back_populates="recruitment",
        cascade="all, delete-orphan",
        order_by="RecruitmentMessage.created_at",
    )


class GameApplication(Base):
    __tablename__ = "game_applications"
    __table_args__ = (
        UniqueConstraint("recruitment_id", "user_id", name="uq_game_application_user"),
        UniqueConstraint("recruitment_id", "character_id", name="uq_game_application_character"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recruitment_id: Mapped[int] = mapped_column(ForeignKey("game_recruitments.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    status: Mapped[str] = mapped_column(String(20), default="applied")

    recruitment = relationship("GameRecruitment", back_populates="applications")
    user = relationship("User")
    character = relationship("Character", back_populates="game_applications")


class RecruitmentMessage(Base):
    __tablename__ = "recruitment_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    recruitment_id: Mapped[int] = mapped_column(ForeignKey("game_recruitments.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    content: Mapped[str] = mapped_column(Text)

    recruitment = relationship("GameRecruitment", back_populates="messages")
