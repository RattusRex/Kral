from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.inventory import add_currency, get_character_inventory, validate_rarity
from app.api.users import get_current_user, get_db
from app.models.character import Character
from app.models.inventory import InventoryItem, ShopTransactionLog
from app.models.user import User
from app.schemas.character import CharacterUpdate
from app.schemas.inventory import (
    AddItemRequest,
    CurrencyUpdateRequest,
    InventoryResponse,
    ShopTransactionLogResponse,
)
from app.schemas.user import KarmaUpdate


router = APIRouter(prefix="/admin")


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin permissions required"
        )
    return current_user


def get_character_or_404(character_id: int, db: Session) -> Character:
    character = db.query(Character).filter(Character.id == character_id).first()
    if not character:
        raise HTTPException(
            status_code=404,
            detail="Character not found"
        )
    return character

def serialize_character(character: Character):
    return {
        "id": character.id,
        "name": character.name,
        "class_name": character.class_name,
        "subclass": character.subclass,
        "race": character.race,
        "background": character.background,
        "route": character.route,
        "level": character.level,
        "xp": character.xp,
        "hp": character.hp,
        "armor_class": character.armor_class,
        "strength": character.strength,
        "dexterity": character.dexterity,
        "constitution": character.constitution,
        "intelligence": character.intelligence,
        "wisdom": character.wisdom,
        "charisma": character.charisma,
        "investigation": character.investigation,
        "is_dead": character.is_dead,
        "user_id": character.user_id,
        "owner_username": character.owner.username,
        "owner_email": character.owner.email
    }


def apply_xp_delta(character: Character, amount: int):
    character.xp = max(0, character.xp + amount)
    if amount <= 0:
        return

    while character.xp >= character.level + 1:
        character.xp -= character.level + 1
        character.level += 1


@router.get("/characters")
def list_characters(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    return [
        serialize_character(character)
        for character in db.query(Character).all()
    ]


@router.get("/characters/{character_id}")
def get_admin_character(
    character_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    return serialize_character(get_character_or_404(character_id, db))


@router.patch("/characters/{character_id}")
def update_admin_character(
    character_id: int,
    character_data: CharacterUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db)
    update_data = character_data.model_dump(exclude_unset=True)

    if "level" in update_data and update_data["level"] is not None:
        update_data["level"] = max(1, update_data["level"])
    if "xp" in update_data and update_data["xp"] is not None:
        update_data["xp"] = max(0, update_data["xp"])

    for key, value in update_data.items():
        setattr(character, key, value)

    db.commit()
    db.refresh(character)
    return serialize_character(character)


@router.get("/characters/{character_id}/inventory", response_model=InventoryResponse)
def get_admin_character_inventory(
    character_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db)
    return get_character_inventory(character.id, character.owner, db)


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    users = db.query(User).all()
    return [{
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "karma": user.karma,
        "is_admin": user.is_admin,
        "character_count": len(user.characters)
    } for user in users]


@router.post("/characters/{character_id}/xp")
def add_character_xp(
    character_id: int,
    xp_data: KarmaUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db)
    apply_xp_delta(character, xp_data.amount)
    db.commit()
    db.refresh(character)
    return character


@router.post("/characters/{character_id}/gold", response_model=InventoryResponse)
def add_character_gold(
    character_id: int,
    gold_data: KarmaUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db)
    inventory = get_character_inventory(character.id, character.owner, db)
    inventory.gold = max(0, inventory.gold + gold_data.amount)
    db.commit()
    db.refresh(inventory)
    return inventory


@router.post("/characters/{character_id}/currency/add", response_model=InventoryResponse)
def add_character_currency(
    character_id: int,
    currency_data: CurrencyUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db)
    inventory = get_character_inventory(character.id, character.owner, db)
    add_currency(
        inventory,
        currency_data.gold,
        currency_data.silver,
        currency_data.copper
    )
    db.commit()
    db.refresh(inventory)
    return inventory


@router.get("/shop-logs", response_model=list[ShopTransactionLogResponse])
def list_shop_logs(
    character_id: int | None = None,
    user_id: int | None = None,
    mode: str | None = None,
    operation_date: date | None = Query(default=None, alias="date"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    query = db.query(ShopTransactionLog)

    if character_id is not None:
        query = query.filter(ShopTransactionLog.character_id == character_id)
    if user_id is not None:
        query = query.filter(ShopTransactionLog.user_id == user_id)
    if mode:
        if mode not in {"buy", "sell"}:
            raise HTTPException(
                status_code=400,
                detail="Unknown shop operation type"
            )
        query = query.filter(ShopTransactionLog.mode == mode)

    if operation_date is not None:
        start = datetime.combine(operation_date, time.min)
        end = start + timedelta(days=1)
        query = query.filter(
            ShopTransactionLog.created_at >= start,
            ShopTransactionLog.created_at < end
        )
    else:
        if date_from is not None:
            query = query.filter(
                ShopTransactionLog.created_at >= datetime.combine(date_from, time.min)
            )
        if date_to is not None:
            query = query.filter(
                ShopTransactionLog.created_at < (
                    datetime.combine(date_to, time.min) + timedelta(days=1)
                )
            )

    return query.order_by(ShopTransactionLog.created_at.desc()).all()


@router.post("/characters/{character_id}/revive")
def revive_character(
    character_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db)
    character.hp = max(character.hp, 1)
    character.is_dead = False
    db.commit()
    db.refresh(character)
    return character


@router.post("/characters/{character_id}/item", response_model=InventoryResponse)
def grant_character_item(
    character_id: int,
    item_data: AddItemRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    validate_rarity(item_data.rarity)
    character = get_character_or_404(character_id, db)
    inventory = get_character_inventory(character.id, character.owner, db)
    db.add(InventoryItem(
        name=item_data.name,
        rarity=item_data.rarity,
        is_consumable=item_data.is_consumable,
        inventory_id=inventory.id
    ))
    db.commit()
    db.refresh(inventory)
    return inventory


def update_user_karma(
    user_id: int,
    amount: int,
    db: Session
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    user.karma = max(0, user.karma + amount)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "karma": user.karma,
        "is_admin": user.is_admin
    }


@router.post("/users/{user_id}/karma")
def change_user_karma(
    user_id: int,
    karma_data: KarmaUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    return update_user_karma(user_id, karma_data.amount, db)


@router.post("/users/{user_id}/karma/add")
def add_user_karma(
    user_id: int,
    karma_data: KarmaUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    return update_user_karma(user_id, karma_data.amount, db)


@router.post("/users/{user_id}/karma/subtract")
def subtract_user_karma(
    user_id: int,
    karma_data: KarmaUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    if karma_data.amount < 0:
        return update_user_karma(user_id, karma_data.amount, db)
    return update_user_karma(user_id, -karma_data.amount, db)
