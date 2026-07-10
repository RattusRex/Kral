from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional

MIN_CHARACTER_LEVEL = 1
MAX_CHARACTER_LEVEL = 20
SKILL_KEYS = {
    "acrobatics", "animal_handling", "arcana", "athletics", "deception",
    "history", "insight", "intimidation", "investigation", "medicine",
    "nature", "perception", "performance", "persuasion", "religion",
    "sleight_of_hand", "stealth", "survival",
}
ABILITY_KEYS = {
    "strength", "dexterity", "constitution",
    "intelligence", "wisdom", "charisma",
}


class SkillSettings(BaseModel):
    skill_proficiencies: Optional[list[str]] = None
    skill_expertise: Optional[list[str]] = None
    saving_throw_proficiencies: Optional[list[str]] = None

    @model_validator(mode="after")
    def validate_skill_settings(self):
        proficiencies = set(self.skill_proficiencies or [])
        expertise = set(self.skill_expertise or [])
        unknown = (proficiencies | expertise) - SKILL_KEYS
        if unknown:
            raise ValueError(f"Неизвестные навыки: {', '.join(sorted(unknown))}")
        if not expertise <= proficiencies:
            raise ValueError("Компетентность требует владения навыком")
        if self.skill_proficiencies is not None:
            self.skill_proficiencies = sorted(proficiencies)
        if self.skill_expertise is not None:
            self.skill_expertise = sorted(expertise)
        saving_throws = set(self.saving_throw_proficiencies or [])
        unknown_saving_throws = saving_throws - ABILITY_KEYS
        if unknown_saving_throws:
            raise ValueError(
                f"Неизвестные спасброски: {', '.join(sorted(unknown_saving_throws))}"
            )
        if self.saving_throw_proficiencies is not None:
            self.saving_throw_proficiencies = sorted(saving_throws)
        return self


class CharacterCreate(SkillSettings):
    model_config = ConfigDict(extra="forbid")

    name: str
    class_name: str
    level: int = Field(ge=MIN_CHARACTER_LEVEL, le=MAX_CHARACTER_LEVEL)
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

class CharacterEditableFields(SkillSettings):
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
    game_created_at: Optional[date] = None
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
    page: int
    page_size: int
    total_entries: int
    pages: int
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
