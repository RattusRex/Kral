from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator, field_validator


MAX_CONTENT_TITLE_LENGTH = 200
MAX_CONTENT_LENGTH = 20_000
MAX_CONTENT_TYPE_LENGTH = 100
MAX_NOTES_LENGTH = 5_000
MAX_RARITY_LENGTH = 50
MAX_SOURCE_LENGTH = 200
ILLEGAL_ITEM_RARITIES = {
    "Обычный", "Необычный", "Редкий", "Очень редкий", "Легендарный", "Артефакт"
}


class ContentBlockCreate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_CONTENT_TITLE_LENGTH)
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "content")
    @classmethod
    def must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ContentBlockUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=MAX_CONTENT_TITLE_LENGTH)
    content: str | None = Field(default=None, min_length=1, max_length=MAX_CONTENT_LENGTH)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "content")
    @classmethod
    def must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ContentBlockOrder(BaseModel):
    block_ids: list[int] = Field(min_length=1)


class ContentBlockResponse(BaseModel):
    id: int
    page_slug: str
    title: str
    content: str
    content_type: str | None = None
    karma_cost: int | None = None
    is_banned: bool = False
    source_url: str | None = None
    rarity: str | None = None
    source: str | None = None
    notes: str | None = None
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HomebrewEntryBase(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_CONTENT_TITLE_LENGTH)
    content_type: str = Field(min_length=1, max_length=MAX_CONTENT_TYPE_LENGTH)
    karma_cost: int | None = Field(default=None, ge=0)
    is_banned: bool = False
    source_url: HttpUrl
    notes: str = Field(default="", max_length=MAX_NOTES_LENGTH)

    @field_validator("title", "content_type", "notes")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_exactly_one_status(self):
        if not self.title or not self.content_type:
            raise ValueError("title and content type must not be blank")
        if self.is_banned == (self.karma_cost is not None):
            raise ValueError("Choose either a karma cost or banned status")
        return self


class HomebrewEntryCreate(HomebrewEntryBase):
    model_config = ConfigDict(extra="forbid")


class HomebrewEntryUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=MAX_CONTENT_TITLE_LENGTH)
    content_type: str | None = Field(default=None, min_length=1, max_length=MAX_CONTENT_TYPE_LENGTH)
    karma_cost: int | None = Field(default=None, ge=0)
    is_banned: bool | None = None
    source_url: HttpUrl | None = None
    notes: str | None = Field(default=None, max_length=MAX_NOTES_LENGTH)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "content_type", "notes")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def normalize_explicit_status(self):
        fields_set = self.model_fields_set
        if self.title == "" or self.content_type == "":
            raise ValueError("title and content type must not be blank")
        if self.is_banned is True and "karma_cost" not in fields_set:
            self.karma_cost = None
            fields_set.add("karma_cost")
        elif self.karma_cost is not None and "is_banned" not in fields_set:
            self.is_banned = False
            fields_set.add("is_banned")
        return self


class IllegalItemBase(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_CONTENT_TITLE_LENGTH)
    rarity: str = Field(min_length=1, max_length=MAX_RARITY_LENGTH)
    source_url: HttpUrl
    source: str = Field(min_length=1, max_length=MAX_SOURCE_LENGTH)

    @field_validator("title", "rarity", "source")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("rarity")
    @classmethod
    def validate_rarity(cls, value: str) -> str:
        if value not in ILLEGAL_ITEM_RARITIES:
            raise ValueError("unknown rarity")
        return value


class IllegalItemCreate(IllegalItemBase):
    model_config = ConfigDict(extra="forbid")


class IllegalItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=MAX_CONTENT_TITLE_LENGTH)
    rarity: str | None = Field(default=None, min_length=1, max_length=MAX_RARITY_LENGTH)
    source_url: HttpUrl | None = None
    source: str | None = Field(default=None, min_length=1, max_length=MAX_SOURCE_LENGTH)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "rarity", "source")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("rarity")
    @classmethod
    def validate_optional_rarity(cls, value: str | None) -> str | None:
        if value is not None and value not in ILLEGAL_ITEM_RARITIES:
            raise ValueError("unknown rarity")
        return value
