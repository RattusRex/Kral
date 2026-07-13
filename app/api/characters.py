import random

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Header
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.core.calendar import GAME_EPOCH
from app.db.database import SessionLocal
from app.models.character import Character
from app.models.user import User
from app.api.users import get_current_user
from app.schemas.character import (
    AbilityRollResponse,
    CharacterCreate,
    PlayerCharacterUpdate,
    SavingThrowRollResponse,
    SkillRollResponse,
)
from app.api.users import get_db
from app.api.projects import get_current_project_access, require_feature
from app.core.projects import require_project_access
from app.models.project import Project

ABILITY_FIELDS = {
    "strength": "Сила",
    "dexterity": "Ловкость",
    "constitution": "Телосложение",
    "intelligence": "Интеллект",
    "wisdom": "Мудрость",
    "charisma": "Харизма",
}

SKILL_FIELDS = {
    "acrobatics": ("Акробатика", "dexterity"),
    "animal_handling": ("Уход за животными", "wisdom"),
    "arcana": ("Магия", "intelligence"),
    "athletics": ("Атлетика", "strength"),
    "deception": ("Обман", "charisma"),
    "history": ("История", "intelligence"),
    "insight": ("Проницательность", "wisdom"),
    "intimidation": ("Запугивание", "charisma"),
    "investigation": ("Расследование", "intelligence"),
    "medicine": ("Медицина", "wisdom"),
    "nature": ("Природа", "intelligence"),
    "perception": ("Восприятие", "wisdom"),
    "performance": ("Выступление", "charisma"),
    "persuasion": ("Убеждение", "charisma"),
    "religion": ("Религия", "intelligence"),
    "sleight_of_hand": ("Ловкость рук", "dexterity"),
    "stealth": ("Скрытность", "dexterity"),
    "survival": ("Выживание", "wisdom"),
}


router = APIRouter()
MAX_CHARACTERS_PER_USER = 10


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


def validate_not_before_epoch(value, label: str):
    if value is not None and value < GAME_EPOCH:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{label} не может быть раньше начала игры "
                f"({GAME_EPOCH.strftime('%d.%m.%Y')})."
            )
        )

@router.post("/characters")
def create_character(
    character_data: CharacterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_project_id: int | None = Header(default=None, alias="X-Project-ID"),
):
    project_id = character_data.project_id
    if project_id is None:
        # Header-less legacy clients are resolved by the same default/single
        # membership rules as other selected-project endpoints.
        project_id = get_current_project_access(x_project_id, current_user, db)[0].id
    require_project_access(db, current_user, project_id)
    character_count = db.query(Character).filter(
        Character.user_id == current_user.id,
        Character.project_id == project_id,
    ).count()
    if character_count >= MAX_CHARACTERS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail="Достигнут лимит персонажей (10 из 10)."
        )

    game_created_at = character_data.game_created_at or GAME_EPOCH
    validate_not_before_epoch(game_created_at, "Дата создания персонажа")

    character = Character(
        name=character_data.name,
        class_name=character_data.class_name,
        class_levels=(
            [entry.model_dump() for entry in character_data.class_levels]
            if character_data.class_levels
            else [{"class_name": character_data.class_name, "level": character_data.level}]
        ),
        game_created_at=game_created_at,
        subclass=character_data.subclass,
        race=character_data.race,
        background=character_data.background,
        strength=character_data.strength,
        dexterity=character_data.dexterity,
        constitution=character_data.constitution,
        intelligence=character_data.intelligence,
        wisdom=character_data.wisdom,
        charisma=character_data.charisma,
        investigation=character_data.investigation,
        skill_proficiencies=character_data.skill_proficiencies or [],
        skill_expertise=character_data.skill_expertise or [],
        saving_throw_proficiencies=(
            character_data.saving_throw_proficiencies or []
        ),
        hp=character_data.hp,
        temp_hp=character_data.temp_hp,
        armor_class=character_data.armor_class,
        speed=character_data.speed,
        level=character_data.level,
        route=character_data.route,
        user_id=current_user.id,
        project_id=project_id,
    )

    db.add(character)

    db.commit()

    db.refresh(character)

    return {
        "id": character.id,
        "project_id": character.project_id,
        "name": character.name,
        "class_name": character.class_name,
        "class_levels": character.class_levels,
        "level": character.level,
        "xp": character.xp,
        "route": character.route,
        "game_created_at": character.game_created_at,
        "subclass": character.subclass,
        "race": character.race,
        "background": character.background,
        "strength": character.strength,
        "dexterity": character.dexterity,
        "constitution": character.constitution,
        "intelligence": character.intelligence,
        "wisdom": character.wisdom,
        "charisma": character.charisma,
        "investigation": character.investigation,
        "skill_proficiencies": character.skill_proficiencies,
        "skill_expertise": character.skill_expertise,
        "saving_throw_proficiencies": character.saving_throw_proficiencies,
        "personal_hireling_enabled": character.personal_hireling_enabled,
        "personal_hireling_acquired_at": character.personal_hireling_acquired_at,
        "personal_hireling_investigation": (
            character.personal_hireling_investigation
        ),
        "simulacrum_enabled": character.simulacrum_enabled,
        "simulacrum_created_at": character.simulacrum_created_at,
        "simulacrum_investigation": character.simulacrum_investigation,
        "hp": character.hp,
        "temp_hp": character.temp_hp,
        "armor_class": character.armor_class,
        "speed": character.speed
    }

@router.get("/characters")
def get_characters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    x_project_id: int | None = Header(default=None, alias="X-Project-ID"),
):
    project, _ = get_current_project_access(x_project_id, current_user, db)
    characters = db.query(Character).filter(
        Character.user_id == current_user.id,
        Character.project_id == project.id,
    ).all()

    return characters


@router.get("/characters/transfer-targets")
def get_transfer_targets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    project: Project = Depends(require_feature("character_transfers")),
):
    query = db.query(Character).filter(Character.project_id == project.id)
    return [{
        "id": character.id,
        "name": character.name,
        "class_name": character.class_name,
        "level": character.level,
        "owner_username": character.owner.username
    } for character in query.all()]


@router.patch("/characters/{character_id}")
def update_character(
    character_id: int,
    character_data: PlayerCharacterUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == current_user.id
    ).first()

    if not character:
        raise HTTPException(
            status_code=404,
            detail="Character not found"
        )

    update_data = character_data.model_dump(exclude_unset=True)

    if "class_levels" in update_data:
        class_levels = update_data["class_levels"]
        update_data["class_name"] = class_levels[0]["class_name"]
        update_data["level"] = sum(entry["level"] for entry in class_levels)
    elif "class_name" in update_data:
        current_levels = character.class_levels or [{
            "class_name": character.class_name,
            "level": character.level,
        }]
        update_data["class_levels"] = [
            {**current_levels[0], "class_name": update_data["class_name"]},
            *current_levels[1:],
        ]

    for key, value in update_data.items():
        setattr(character, key, value)

    db.commit()
    db.refresh(character)

    return character


@router.post(
    "/characters/{character_id}/roll-ability/{ability}",
    response_model=AbilityRollResponse
)
def roll_ability(
    character_id: int,
    ability: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if ability not in ABILITY_FIELDS:
        raise HTTPException(status_code=400, detail="Неизвестная характеристика")

    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == current_user.id
    ).first()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")

    score = getattr(character, ability)
    modifier = (score - 10) // 2
    roll = random.randint(1, 20)
    total = roll + modifier
    mod_text = f"{'+' if modifier >= 0 else ''}{modifier}"
    ability_label = ABILITY_FIELDS[ability]

    from app.api.chat import create_roll_chat_message
    create_roll_chat_message(
        db=db,
        user=current_user,
        formula=f"1d20{mod_text}",
        rolls=[roll],
        total=total,
        content=(
            f"{current_user.username}: {character.name} — бросок {ability_label}. "
            f"Бросок: {roll}. Модификатор: {mod_text}. Итог: {total}."
        )
    )
    db.commit()

    return {
        "ability": ability,
        "score": score,
        "modifier": modifier,
        "roll": roll,
        "total": total,
    }


@router.post(
    "/characters/{character_id}/roll-saving-throw/{ability}",
    response_model=SavingThrowRollResponse
)
def roll_saving_throw(
    character_id: int,
    ability: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if ability not in ABILITY_FIELDS:
        raise HTTPException(status_code=400, detail="Неизвестная характеристика")

    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == current_user.id
    ).first()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")

    score = getattr(character, ability)
    bonus = (score - 10) // 2
    if ability in (character.saving_throw_proficiencies or []):
        bonus += 2 + (max(1, min(20, character.level)) - 1) // 4
    roll = random.randint(1, 20)
    total = roll + bonus
    bonus_text = f"{'+' if bonus >= 0 else ''}{bonus}"
    ability_label = ABILITY_FIELDS[ability]

    from app.api.chat import create_roll_chat_message
    create_roll_chat_message(
        db=db,
        user=current_user,
        formula=f"1d20{bonus_text}",
        rolls=[roll],
        total=total,
        content=(
            f"{current_user.username}: {character.name} — спасбросок {ability_label}. "
            f"Бросок: {roll}. Бонус: {bonus_text}. Итог: {total}."
        )
    )
    db.commit()

    return {
        "ability": ability,
        "bonus": bonus,
        "roll": roll,
        "total": total,
    }


@router.post(
    "/characters/{character_id}/roll-skill/{skill}",
    response_model=SkillRollResponse,
)
def roll_skill(
    character_id: int,
    skill: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    skill_definition = SKILL_FIELDS.get(skill)
    if not skill_definition:
        raise HTTPException(status_code=400, detail="Неизвестный навык")

    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == current_user.id,
    ).first()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")

    skill_label, ability = skill_definition
    modifier = (getattr(character, ability) - 10) // 2
    proficiency_bonus = 2 + (max(1, min(20, character.level)) - 1) // 4
    if skill in (character.skill_expertise or []):
        modifier += proficiency_bonus * 2
    elif skill in (character.skill_proficiencies or []):
        modifier += proficiency_bonus

    roll = random.randint(1, 20)
    total = roll + modifier
    modifier_text = f"{'+' if modifier >= 0 else ''}{modifier}"

    from app.api.chat import create_roll_chat_message
    create_roll_chat_message(
        db=db,
        user=current_user,
        formula=f"1d20{modifier_text}",
        rolls=[roll],
        total=total,
        content=(
            f"{current_user.username}: {character.name} — навык {skill_label}. "
            f"Формула: 1d20{modifier_text}. Бросок: {roll}. Итог: {total}."
        ),
    )
    db.commit()

    return {
        "skill": skill,
        "ability": ability,
        "modifier": modifier,
        "roll": roll,
        "total": total,
    }
