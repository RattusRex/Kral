from sqlalchemy import Boolean, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.roles import Role
from app.db.database import Base


DEFAULT_FEATURES = {
    "shop": True,
    "market": True,
    "karma_shop": True,
    "recruitments": True,
    "personal_hirelings": True,
    "simulacrums": True,
}


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    features: Mapped[dict] = mapped_column(JSON, default=lambda: dict(DEFAULT_FEATURES))

    memberships = relationship("ProjectMembership", back_populates="project", cascade="all, delete-orphan")


class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_membership"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), default=Role.PLAYER)

    project = relationship("Project", back_populates="memberships")
    user = relationship("User", back_populates="project_memberships")
