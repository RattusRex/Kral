from pydantic import BaseModel, ConfigDict
from typing import Optional

class CharacterCreate(BaseModel):
    name: str
    class_name: str
    level: int
    route: str
    subclass: str = ""
    race: str = ""
    background: str = ""
    strength: int = 8
    dexterity: int = 8
    constitution: int = 8
    intelligence: int = 8
    wisdom: int = 8
    charisma: int = 8
    investigation: int = 0
    hp: int = 0
    temp_hp: int = 0
    armor_class: int = 9
    speed: int = 30

class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    class_name: Optional[str] = None
    level: Optional[int] = None
    xp: Optional[int] = None
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
    investigation: Optional[int] = None
    hp: Optional[int] = None
    temp_hp: Optional[int] = None
    armor_class: Optional[int] = None
    speed: Optional[int] = None
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
