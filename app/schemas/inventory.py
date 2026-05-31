from pydantic import BaseModel
from typing import List
from pydantic import ConfigDict


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
    items: List[InventoryItemResponse] = []

    model_config = ConfigDict(from_attributes=True)


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
