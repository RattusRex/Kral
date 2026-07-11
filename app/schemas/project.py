from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120, pattern=r".*\S.*")


class ProjectMembershipCreate(BaseModel):
    user_id: int
    role: str = "player"


class ProjectMembershipUpdate(BaseModel):
    role: str
