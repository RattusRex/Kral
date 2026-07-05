from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from app.db.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Inventory(Base):
    __tablename__ = "inventories"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    gold: Mapped[int] = mapped_column(
        default=0
    )

    silver: Mapped[int] = mapped_column(
        default=0
    )

    copper: Mapped[int] = mapped_column(
        default=0
    )

    notes: Mapped[str] = mapped_column(
        Text,
        default=""
    )

    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id"),
        unique=True
    )
    character = relationship(
        "Character",
        back_populates="inventory"
    )

    items = relationship(
        "InventoryItem",
        back_populates="inventory",
        cascade="all, delete-orphan"
    )

    shop_quotes = relationship(
        "ShopQuote",
        back_populates="inventory",
        cascade="all, delete-orphan"
    )

    shop_transaction_logs = relationship(
        "ShopTransactionLog",
        back_populates="inventory"
    )


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(255)
    )

    rarity: Mapped[str] = mapped_column(
        String(50),
        default="Обычный"
    )

    is_consumable: Mapped[bool] = mapped_column(
        default=False
    )

    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventories.id")
    )
    inventory = relationship(
        "Inventory",
        back_populates="items"
    )


class ShopQuote(Base):
    __tablename__ = "shop_quotes"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    mode: Mapped[str] = mapped_column(
        String(10)
    )

    item_name: Mapped[str] = mapped_column(
        String(255)
    )

    rarity: Mapped[str] = mapped_column(
        String(50)
    )

    is_consumable: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    item_id: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    searcher_type: Mapped[str] = mapped_column(
        String(32),
        default="character"
    )

    success: Mapped[bool] = mapped_column(
        Boolean
    )

    search_roll: Mapped[int]
    modifier: Mapped[int]
    total_roll: Mapped[int]
    dc: Mapped[int]
    days: Mapped[int]
    hireling_cost: Mapped[int]

    price_roll: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    multiplier: Mapped[float] = mapped_column(
        Float,
        nullable=True
    )

    item_price: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    is_consumed: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventories.id")
    )
    inventory = relationship(
        "Inventory",
        back_populates="shop_quotes"
    )


class ShopTransactionLog(Base):
    __tablename__ = "shop_transaction_logs"

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

    username: Mapped[str] = mapped_column(
        String(50)
    )

    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id")
    )

    character_name: Mapped[str] = mapped_column(
        String(255)
    )

    inventory_id: Mapped[int] = mapped_column(
        ForeignKey("inventories.id")
    )

    mode: Mapped[str] = mapped_column(
        String(10)
    )

    item_name: Mapped[str] = mapped_column(
        String(255)
    )

    rarity: Mapped[str] = mapped_column(
        String(50)
    )

    item_price: Mapped[int]
    hireling_cost: Mapped[int]
    total_amount: Mapped[int]

    user = relationship(
        "User",
        back_populates="shop_transaction_logs"
    )

    character = relationship(
        "Character",
        back_populates="shop_transaction_logs"
    )

    inventory = relationship(
        "Inventory",
        back_populates="shop_transaction_logs"
    )


class TransferLog(Base):
    __tablename__ = "transfer_logs"

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

    username: Mapped[str] = mapped_column(
        String(50)
    )

    sender_character_id: Mapped[int] = mapped_column(
        Integer
    )

    sender_character_name: Mapped[str] = mapped_column(
        String(255)
    )

    recipient_character_id: Mapped[int] = mapped_column(
        Integer
    )

    recipient_character_name: Mapped[str] = mapped_column(
        String(255)
    )

    transfer_type: Mapped[str] = mapped_column(
        String(20)
    )

    gold: Mapped[int] = mapped_column(
        default=0
    )

    silver: Mapped[int] = mapped_column(
        default=0
    )

    copper: Mapped[int] = mapped_column(
        default=0
    )

    item_name = mapped_column(
        String(255),
        nullable=True
    )

    item_rarity = mapped_column(
        String(50),
        nullable=True
    )

    item_is_consumable = mapped_column(
        Boolean,
        nullable=True
    )
