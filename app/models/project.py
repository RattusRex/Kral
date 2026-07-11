from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


DEFAULT_PROJECT_NAME = "Эпоха Катастроф"
PROJECT_ADMIN = "admin"
PROJECT_PLAYER = "player"
PROJECT_ROLES = (PROJECT_ADMIN, PROJECT_PLAYER)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    owner = relationship("User", foreign_keys=[owner_id])
    memberships = relationship(
        "ProjectMembership", back_populates="project", cascade="all, delete-orphan"
    )
    characters = relationship("Character", back_populates="project")


class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_membership_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), default=PROJECT_PLAYER)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    project = relationship("Project", back_populates="memberships")
    user = relationship("User", back_populates="project_memberships")
