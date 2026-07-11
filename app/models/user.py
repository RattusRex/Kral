from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.core.roles import (
    Role,
    is_admin_role,
    is_owner_role,
    is_head_admin_role,
)



class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True
    )

    hashed_password: Mapped[str]

    karma: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    role: Mapped[str] = mapped_column(
        String(20),
        default=Role.PLAYER,
        server_default=Role.PLAYER
    )

    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    email_verification_token_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        unique=True,
    )
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def is_admin(self) -> bool:
        """True for owners, head admins and admins (game-master tools access)."""
        return is_admin_role(self.role)

    @property
    def is_owner(self) -> bool:
        return is_owner_role(self.role)

    @property
    def is_head_admin(self) -> bool:
        return is_head_admin_role(self.role)

    characters = relationship(
        "Character",
        back_populates="owner"
    )

    shop_transaction_logs = relationship(
        "ShopTransactionLog",
        back_populates="user"
    )

    project_memberships = relationship(
        "ProjectMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )
