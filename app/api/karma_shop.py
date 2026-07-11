from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.admin import apply_xp_delta
from app.api.users import get_current_user, get_db
from app.models.character import Character
from app.models.inventory import KarmaPurchase
from app.models.user import User
from app.schemas.karma_shop import (
    KarmaItemPurchaseRequest,
    KarmaPurchaseResponse,
    KarmaPurchaseResult,
    KarmaResurrectionRequest,
    KarmaXpPurchaseRequest,
)

router = APIRouter(prefix="/karma-shop")
XP_KARMA_COST = 5


def owned_character(character_id: int, user: User, db: Session) -> Character:
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == user.id,
    ).first()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    return character


def charge_karma(user: User, cost: int) -> None:
    if user.karma < cost:
        raise HTTPException(status_code=400, detail="Недостаточно кармы")
    user.karma -= cost


def record_purchase(
    db: Session,
    user: User,
    purchase_type: str,
    name: str,
    cost: int,
    character: Character | None = None,
) -> KarmaPurchase:
    purchase = KarmaPurchase(
        user_id=user.id,
        username=user.username,
        actor_id=user.id,
        actor_username=user.username,
        character_id=character.id if character else None,
        character_name=character.name if character else None,
        character_level=character.level if character else None,
        purchase_type=purchase_type,
        name=name,
        cost=cost,
    )
    db.add(purchase)
    return purchase


def commit_result(
    db: Session,
    user: User,
    purchase: KarmaPurchase,
    character: Character | None = None,
) -> dict:
    db.commit()
    db.refresh(purchase)
    db.refresh(user)
    if character:
        db.refresh(character)
    return {
        "purchase": purchase,
        "remaining_karma": user.karma,
        "character_level": character.level if character else None,
        "character_xp": character.xp if character else None,
        "character_is_dead": character.is_dead if character else None,
    }


@router.get("/purchases", response_model=list[KarmaPurchaseResponse])
def list_owned_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(KarmaPurchase).filter(
        KarmaPurchase.user_id == current_user.id,
        KarmaPurchase.purchase_type.in_(("item", "opener")),
    ).order_by(KarmaPurchase.created_at.desc(), KarmaPurchase.id.desc()).all()


@router.post("/xp", response_model=KarmaPurchaseResult)
def purchase_xp(
    request: KarmaXpPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    character = owned_character(request.character_id, current_user, db)
    cost = request.amount * XP_KARMA_COST
    charge_karma(current_user, cost)
    apply_xp_delta(character, request.amount)
    purchase = record_purchase(
        db, current_user, "xp", f"{request.amount} опыта", cost, character,
    )
    return commit_result(db, current_user, purchase, character)


@router.post("/purchases", response_model=KarmaPurchaseResult)
def purchase_item(
    request: KarmaItemPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    charge_karma(current_user, request.cost)
    purchase = record_purchase(
        db, current_user, request.purchase_type, request.name, request.cost,
    )
    return commit_result(db, current_user, purchase)


@router.post("/resurrect", response_model=KarmaPurchaseResult)
def resurrect_character(
    request: KarmaResurrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    character = owned_character(request.character_id, current_user, db)
    if not character.is_dead:
        raise HTTPException(status_code=400, detail="Персонаж не погиб")
    if character.level >= 11:
        raise HTTPException(
            status_code=400,
            detail="Воскрешение недоступно персонажам 11 уровня и выше",
        )
    cost = 5 if character.level <= 5 else 10
    charge_karma(current_user, cost)
    character.is_dead = False
    purchase = record_purchase(
        db, current_user, "resurrection", "Воскрешение персонажа", cost, character,
    )
    return commit_result(db, current_user, purchase, character)
