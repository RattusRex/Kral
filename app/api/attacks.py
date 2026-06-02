import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.chat import create_roll_chat_message
from app.api.users import get_current_user, get_db
from app.models.character import Character, CharacterAttack
from app.models.user import User
from app.schemas.character import (
    AttackRollResponse,
    CharacterAttackCreate,
    CharacterAttackResponse,
    CharacterAttackUpdate,
)


router = APIRouter()


def get_character_for_current_user(
    character_id: int,
    current_user: User,
    db: Session
) -> Character:
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == current_user.id
    ).first()

    if not character:
        raise HTTPException(
            status_code=404,
            detail="Персонаж не найден"
        )

    return character


def get_attack_for_character(
    character: Character,
    attack_id: int,
    db: Session
) -> CharacterAttack:
    attack = db.query(CharacterAttack).filter(
        CharacterAttack.id == attack_id,
        CharacterAttack.character_id == character.id
    ).first()

    if not attack:
        raise HTTPException(
            status_code=404,
            detail="Атака не найдена"
        )

    return attack


def require_attack_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="Attack name is required"
        )
    return normalized


@router.get(
    "/characters/{character_id}/attacks",
    response_model=list[CharacterAttackResponse]
)
def list_attacks(
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = get_character_for_current_user(character_id, current_user, db)
    return db.query(CharacterAttack).filter(
        CharacterAttack.character_id == character.id
    ).order_by(CharacterAttack.id.asc()).all()


@router.post(
    "/characters/{character_id}/attacks",
    response_model=CharacterAttackResponse
)
def create_attack(
    character_id: int,
    attack_data: CharacterAttackCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = get_character_for_current_user(character_id, current_user, db)
    attack = CharacterAttack(
        character_id=character.id,
        name=require_attack_name(attack_data.name),
        attack_bonus=attack_data.attack_bonus,
        damage=attack_data.damage
    )
    db.add(attack)
    db.commit()
    db.refresh(attack)
    return attack


@router.patch(
    "/characters/{character_id}/attacks/{attack_id}",
    response_model=CharacterAttackResponse
)
def update_attack(
    character_id: int,
    attack_id: int,
    attack_data: CharacterAttackUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = get_character_for_current_user(character_id, current_user, db)
    attack = get_attack_for_character(character, attack_id, db)
    update_data = attack_data.model_dump(exclude_unset=True)
    if "name" in update_data:
        update_data["name"] = require_attack_name(update_data["name"])

    for key, value in update_data.items():
        setattr(attack, key, value)

    db.commit()
    db.refresh(attack)
    return attack


@router.delete("/characters/{character_id}/attacks/{attack_id}")
def delete_attack(
    character_id: int,
    attack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = get_character_for_current_user(character_id, current_user, db)
    attack = get_attack_for_character(character, attack_id, db)
    db.delete(attack)
    db.commit()
    return {"deleted": True, "id": attack_id}


@router.post(
    "/characters/{character_id}/attacks/{attack_id}/roll",
    response_model=AttackRollResponse
)
def roll_attack(
    character_id: int,
    attack_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = get_character_for_current_user(character_id, current_user, db)
    attack = get_attack_for_character(character, attack_id, db)
    attack_roll = random.randint(1, 20)
    total = attack_roll + attack.attack_bonus
    bonus_text = f"+{attack.attack_bonus}" if attack.attack_bonus >= 0 else str(attack.attack_bonus)
    create_roll_chat_message(
        db=db,
        user=current_user,
        formula=f"1d20{bonus_text}",
        rolls=[attack_roll],
        total=total,
        content=(
            f"{current_user.username}: {character.name} атакует {attack.name}. "
            f"Бросок: {attack_roll}. Бонус: {bonus_text}. Итог: {total}."
        )
    )
    db.commit()

    return {
        "attack_id": attack.id,
        "name": attack.name,
        "roll": attack_roll,
        "bonus": attack.attack_bonus,
        "total": total,
        "damage": attack.damage
    }
