from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectAboutPostCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20_000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "content")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ProjectAboutPostUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=20_000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "content")
    @classmethod
    def text_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ProjectAboutPostResponse(BaseModel):
    id: int
    title: str
    content: str
    position: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProjectAboutCreatorUpdate(BaseModel):
    content: str = Field(default="", max_length=20_000)

    model_config = ConfigDict(extra="forbid")


class ProjectAboutCreatorResponse(BaseModel):
    content: str


class ProjectAboutResponse(BaseModel):
    posts: list[ProjectAboutPostResponse]
    creator_content: str


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$"
    )


class ProjectRoleUpdate(BaseModel):
    role: str


class ProjectFeaturesUpdate(BaseModel):
    features: dict[str, bool]


class ProjectAvailabilityUpdate(BaseModel):
    is_selectable: bool
