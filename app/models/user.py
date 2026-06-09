from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.core.roles import Role, is_admin_role, is_owner_role



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

    @property
    def is_admin(self) -> bool:
        """True for owners and admins (game-master tools access)."""
        return is_admin_role(self.role)

    @property
    def is_owner(self) -> bool:
        return is_owner_role(self.role)

    characters = relationship(
        "Character",
        back_populates="owner"
    )

    shop_transaction_logs = relationship(
        "ShopTransactionLog",
        back_populates="user"
    )
