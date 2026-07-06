from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class CharacterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    class_name: str
    level: int
    route: str
    game_created_at: Optional[date] = None
    subclass: str = ""
    race: str = ""
    background: str = ""
    strength: int = 8
    dexterity: int = 8
    constitution: int = 8
    intelligence: int = 8
    wisdom: int = 8
    charisma: int = 8
    investigation: int = Field(default=0, title="Расследование")
    hp: int = 0
    temp_hp: int = 0
    armor_class: int = 9
    speed: int = 30

class CharacterEditableFields(BaseModel):
    name: Optional[str] = None
    class_name: Optional[str] = None
    route: Optional[str] = None
    subclass: Optional[str] = None
    race: Optional[str] = None
    background: Optional[str] = None
    strength: Optional[int] = None
    dexterity: Optional[int] = None
    constitution: Optional[int] = None
    intelligence: Optional[int] = None
    wisdom: Optional[int] = None
    charisma: Optional[int] = None
    investigation: Optional[int] = Field(default=None, title="Расследование")
    hp: Optional[int] = None
    temp_hp: Optional[int] = None
    armor_class: Optional[int] = None
    speed: Optional[int] = None


class PlayerCharacterUpdate(CharacterEditableFields):
    model_config = ConfigDict(extra="forbid")


class CharacterUpdate(CharacterEditableFields):
    personal_hireling_enabled: Optional[bool] = None
    personal_hireling_acquired_at: Optional[date] = None
    personal_hireling_investigation: Optional[int] = Field(default=None, title="Расследование личного наёмника")
    simulacrum_enabled: Optional[bool] = None
    simulacrum_created_at: Optional[date] = None
    simulacrum_investigation: Optional[int] = Field(default=None, title="Расследование симулякра")
    level: Optional[int] = None
    xp: Optional[int] = None
    is_dead: Optional[bool] = None


class CharacterAttackCreate(BaseModel):
    name: str
    attack_bonus: int = 0
    damage: str = ""


class CharacterAttackUpdate(BaseModel):
    name: Optional[str] = None
    attack_bonus: Optional[int] = None
    damage: Optional[str] = None


class CharacterAttackResponse(BaseModel):
    id: int
    character_id: int
    name: str
    attack_bonus: int
    damage: str

    model_config = ConfigDict(from_attributes=True)


class AttackRollResponse(BaseModel):
    attack_id: int
    name: str
    roll: int
    bonus: int
    total: int
    damage: str


class DamageRollResponse(BaseModel):
    attack_id: int
    name: str
    formula: str
    rolls: list[int]
    modifier: int
    total: int


class AbilityRollResponse(BaseModel):
    ability: str
    score: int
    modifier: int
    roll: int
    total: int


class SavingThrowRollResponse(BaseModel):
    ability: str
    bonus: int
    roll: int
    total: int


class DowntimeEntryCreate(BaseModel):
    start_date: date
    days: int
    reason: str = ""


class DowntimeEntryUpdate(BaseModel):
    start_date: Optional[date] = None
    days: Optional[int] = None
    reason: Optional[str] = None


class DowntimeEntryResponse(BaseModel):
    id: int
    character_id: int
    start_date: date
    days: int
    reason: str
    source: str
    agent_type: str

    model_config = ConfigDict(from_attributes=True)


class CalendarSummaryResponse(BaseModel):
    game_epoch: date
    created_at: date
    current_date: date
    total_days: int
    busy_days: int
    free_days: int
    can_manage: bool = False
    entries: list[DowntimeEntryResponse]


class CalendarAuditLogResponse(BaseModel):
    id: int
    created_at: datetime
    user_id: int
    username: str
    role: str
    character_id: int
    character_name: str
    action: str
    entry_id: Optional[int] = None
    details: str

    model_config = ConfigDict(from_attributes=True)
