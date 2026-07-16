from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProjectAboutUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=20_000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class ProjectAboutResponse(BaseModel):
    title: str
    description: str


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
