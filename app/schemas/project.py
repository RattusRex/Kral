from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$"
    )


class ProjectRoleUpdate(BaseModel):
    role: str


class ProjectFeaturesUpdate(BaseModel):
    features: dict[str, bool]
