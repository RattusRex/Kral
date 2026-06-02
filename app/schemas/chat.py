from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatMessageCreate(BaseModel):
    content: str


class DiceRollRequest(BaseModel):
    formula: str


class ChatMessageResponse(BaseModel):
    id: int
    created_at: datetime
    user_id: int
    username: str
    channel: str
    content: str
    formula: str | None
    rolls: list[int] | None
    total: int | None

    model_config = ConfigDict(from_attributes=True)
