from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_PROJECT_ABOUT_TITLE_LENGTH = 200
MAX_PROJECT_ABOUT_DESCRIPTION_LENGTH = 20_000


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


class ProjectAboutUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_PROJECT_ABOUT_TITLE_LENGTH)
    description: str = Field(default="", max_length=MAX_PROJECT_ABOUT_DESCRIPTION_LENGTH)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title")
    @classmethod
    def title_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value
