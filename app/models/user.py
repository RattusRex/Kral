from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm import relationship
from app.db.database import Base



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

    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    characters = relationship(
        "Character",
        back_populates="owner"
    )

