from pydantic import BaseModel
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
    armor_class: int = 9

class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    class_name: Optional[str] = None
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
    armor_class: Optional[int] = None
    is_dead: Optional[bool] = None


