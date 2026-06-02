from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Boolean
from app.db.database import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str]

    class_name: Mapped[str]

    subclass: Mapped[str] = mapped_column(
        default=""
    )

    race: Mapped[str] = mapped_column(
        default=""
    )

    background: Mapped[str] = mapped_column(
        default=""
    )

    strength: Mapped[int] = mapped_column(
        default=10
    )

    dexterity: Mapped[int] = mapped_column(
        default=10
    )

    constitution: Mapped[int] = mapped_column(
        default=10
    )

    intelligence: Mapped[int] = mapped_column(
        default=10
    )

    wisdom: Mapped[int] = mapped_column(
        default=10
    )

    charisma: Mapped[int] = mapped_column(
        default=10
    )

    investigation: Mapped[int] = mapped_column(
        default=0
    )

    hp: Mapped[int] = mapped_column(
        default=0
    )

    temp_hp: Mapped[int] = mapped_column(
        default=0
    )

    armor_class: Mapped[int] = mapped_column(
        default=10
    )

    speed: Mapped[int] = mapped_column(
        default=30
    )

    level: Mapped[int] = mapped_column(
        default=1
    )

    xp: Mapped[int] = mapped_column(
        default=0
    )

    is_dead: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    route: Mapped[str]


    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )
    owner = relationship(
        "User",
        back_populates="characters"
    )

    inventory = relationship(
        "Inventory",
        back_populates="character",
        uselist=False,
        cascade="all, delete-orphan"
    )

    shop_transaction_logs = relationship(
        "ShopTransactionLog",
        back_populates="character"
    )

    attacks = relationship(
        "CharacterAttack",
        back_populates="character",
        cascade="all, delete-orphan"
    )


class CharacterAttack(Base):
    __tablename__ = "character_attacks"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(255)
    )

    attack_bonus: Mapped[int] = mapped_column(
        default=0
    )

    damage: Mapped[str] = mapped_column(
        String(255),
        default=""
    )

    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id")
    )
    character = relationship(
        "Character",
        back_populates="attacks"
    )
