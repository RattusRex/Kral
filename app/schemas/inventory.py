from pydantic import BaseModel
from typing import List
from pydantic import ConfigDict
from datetime import datetime


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


class MagicItemResponse(BaseModel):
    id: int
    name: str
    rarity: str
    raw_rarity: str
    type: str
    source: str | None = None
    page: int | None = None
    tier: str | None = None
    requires_attunement: bool = False
    attunement_note: str | None = None
    is_consumable: bool = False
    description: str = ""


class AddItemRequest(BaseModel):
    name: str
    rarity: str = "Обычный"
    is_consumable: bool = False


class GoldUpdateRequest(BaseModel):
    amount: int

class CurrencyUpdateRequest(BaseModel):
    gold: int = 0
    silver: int = 0
    copper: int = 0

class InventoryNotesUpdateRequest(BaseModel):
    notes: str = ""

class CurrencyTransferRequest(CurrencyUpdateRequest):
    recipient_character_id: int

class ItemTransferRequest(BaseModel):
    recipient_character_id: int
    item_id: int

class ShopSearchRequest(BaseModel):
    mode: str = "buy"
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

class ShopResult(BaseModel):
    quote_id: int | None = None
    mode: str
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
    character_id: int
    character_name: str
    mode: str
    item_name: str
    rarity: str
    item_price: int
    hireling_cost: int
    total_amount: int

    model_config = ConfigDict(from_attributes=True)


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
