from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KarmaXpPurchaseRequest(BaseModel):
    character_id: int
    amount: int = Field(ge=1, le=1000)


class KarmaOpener(BaseModel):
    name: str
    cost: int
    note: str | None = None


class AdminOpenerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    cost: int = Field(default=0, ge=0, le=1_000_000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Название открывашки обязательно")
        return normalized


class KarmaItemPurchaseRequest(BaseModel):
    purchase_type: Literal["item", "opener"]
    name: str = Field(min_length=1, max_length=255)
    cost: int = Field(ge=1, le=1_000_000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Название покупки обязательно")
        return normalized


class KarmaResurrectionRequest(BaseModel):
    character_id: int


class KarmaPurchaseResponse(BaseModel):
    id: int
    created_at: datetime
    user_id: int | None
    username: str
    actor_id: int | None = None
    actor_username: str | None = None
    character_id: int | None
    character_name: str | None
    character_level: int | None
    purchase_type: str
    name: str
    cost: int

    model_config = ConfigDict(from_attributes=True)


class KarmaPurchaseResult(BaseModel):
    purchase: KarmaPurchaseResponse
    remaining_karma: int
    character_level: int | None = None
    character_xp: int | None = None
    character_is_dead: bool | None = None
