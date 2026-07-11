from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_CONTENT_TITLE_LENGTH = 200
MAX_CONTENT_LENGTH = 20_000


class ContentBlockCreate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_CONTENT_TITLE_LENGTH)
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)

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
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
