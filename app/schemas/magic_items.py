from pydantic import BaseModel


class MagicItemResponse(BaseModel):
    id: str
    name: str
    rarity: str
    rarity_key: str
    item_type: str
    raw_type: str
    source: str
    page: int | None = None
    tier: str | None = None
    requires: list[str]
    is_consumable: bool


class MagicItemFilterOptions(BaseModel):
    rarities: list[str]
    item_types: list[str]
