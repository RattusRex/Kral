from pydantic import BaseModel, Field
from typing import Any, List
from pydantic import ConfigDict
from datetime import datetime

from app.core.text_limits import MAX_INVENTORY_NOTES_LENGTH


class InventoryItemResponse(BaseModel):
    id: int
    name: str
    rarity: str
    is_consumable: bool

    model_config = ConfigDict(from_attributes=True)


class InventoryResponse(BaseModel):
    id: int
    character_id: int
    gold: int
    silver: int
    copper: int
    notes: str = ""
    items: List[InventoryItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


class AddItemRequest(BaseModel):
    name: str
    rarity: str = "Обычный"
    is_consumable: bool = False


class AdminAddItemRequest(AddItemRequest):
    reason: str = Field(min_length=1, max_length=1000, pattern=r".*\S.*")


class GoldUpdateRequest(BaseModel):
    amount: int

class CurrencyUpdateRequest(BaseModel):
    gold: int = 0
    silver: int = 0
    copper: int = 0

class AdminCurrencyUpdateRequest(CurrencyUpdateRequest):
    reason: str = Field(min_length=1, max_length=1000, pattern=r".*\S.*")

class InventoryNotesUpdateRequest(BaseModel):
    notes: str = Field(default="", max_length=MAX_INVENTORY_NOTES_LENGTH)

class CurrencyTransferRequest(CurrencyUpdateRequest):
    recipient_character_id: int

class ItemTransferRequest(BaseModel):
    recipient_character_id: int
    item_id: int

class ShopSearchRequest(BaseModel):
    mode: str = "buy"
    magic_item_id: str | None = None
    item_name: str | None = None
    rarity: str | None = None
    is_consumable: bool = False
    item_id: int | None = None
    searcher_type: str = "character"
    hireling_level: str = "Плохой"

class ShopBuyRequest(ShopSearchRequest):
    pass

class ShopSellRequest(BaseModel):
    item_id: int
    searcher_type: str = "character"
    hireling_level: str = "Плохой"

class ShopConfirmRequest(BaseModel):
    quote_id: int

class ShopTransactionRequest(BaseModel):
    item_name: str
    item_price: int
    mercenary_cost: int = 0

class MagicItemResponse(BaseModel):
    id: str
    name: str
    rarity: str
    rarity_key: str
    item_type: str
    source: str | None = None
    page: int | None = None
    tier: str | None = None
    is_consumable: bool = False
    reference_sources: List[str] = Field(default_factory=list)
    requires: List[dict[str, Any]] = Field(default_factory=list)
    entries: List[str] = Field(default_factory=list)

class ShopResult(BaseModel):
    quote_id: int | None = None
    mode: str
    searcher_type: str
    searcher_label: str
    item_name: str
    rarity: str
    is_consumable: bool
    success: bool
    search_roll: int
    modifier: int
    total_roll: int
    dc: int
    days: int
    hireling_cost: int
    price_roll: int | None
    multiplier: float | None
    item_price: int | None
    total_cost: int | None
    is_consumed: bool
    inventory: InventoryResponse


class ShopTransactionLogResponse(BaseModel):
    id: int
    created_at: datetime
    user_id: int
    username: str
    actor_id: int | None = None
    actor_username: str | None = None
    character_id: int
    character_name: str
    mode: str
    item_name: str
    rarity: str
    item_price: int
    hireling_cost: int
    total_amount: int
    total_copper: int | None = None

    model_config = ConfigDict(from_attributes=True)


class MarketSaleRequest(BaseModel):
    item_name: str = Field(min_length=1, max_length=255, pattern=r".*\S.*")
    gold: int = Field(gt=0)


class MarketSaleLogResponse(BaseModel):
    id: int
    created_at: datetime
    user_id: int
    username: str
    actor_id: int | None = None
    actor_username: str | None = None
    character_id: int
    character_name: str
    item_name: str
    gold: int

    model_config = ConfigDict(from_attributes=True)


class MarketSaleResponse(BaseModel):
    sale: MarketSaleLogResponse
    inventory: InventoryResponse


class TransferLogResponse(BaseModel):
    id: int
    created_at: datetime
    user_id: int
    username: str
    sender_character_id: int
    sender_character_name: str
    recipient_character_id: int
    recipient_character_name: str
    transfer_type: str
    gold: int
    silver: int
    copper: int
    item_name: str | None
    item_rarity: str | None
    item_is_consumable: bool | None

    model_config = ConfigDict(from_attributes=True)


class AdminGrantLogResponse(BaseModel):
    id: int
    created_at: datetime
    admin_id: int
    admin_username: str
    user_id: int
    username: str
    character_id: int | None
    character_name: str | None
    operation_type: str
    value: str
    reason: str

    model_config = ConfigDict(from_attributes=True)
