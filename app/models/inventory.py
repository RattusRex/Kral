from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from app.db.database import Base


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
