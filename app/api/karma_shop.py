from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.admin import apply_xp_delta
from app.api.projects import require_feature
from app.api.users import get_current_user, get_db
from app.models.character import Character
from app.models.inventory import KarmaPurchase
from app.models.project import Project, ProjectMembership
from app.api.projects import get_current_project_access
from app.models.user import User
from app.schemas.karma_shop import (
    KarmaItemPurchaseRequest,
    KarmaOpener,
    KarmaPurchaseResponse,
    KarmaPurchaseResult,
    KarmaResurrectionRequest,
    KarmaXpPurchaseRequest,
)

router = APIRouter(
    prefix="/karma-shop",
    dependencies=[Depends(require_feature("karma")), Depends(require_feature("karma_shop"))],
)
XP_KARMA_COST = 5
OPENER_NOTE = "Условия применения проверяются администрацией или мастером."
OPENER_CATALOG = (
    KarmaOpener(name="Смена расы", cost=10, note=OPENER_NOTE),
    KarmaOpener(name="Смена класса", cost=20, note=OPENER_NOTE),
    KarmaOpener(name="Смена подкласса", cost=15, note=OPENER_NOTE),
    KarmaOpener(name="Смена черты", cost=10, note=OPENER_NOTE),
    KarmaOpener(name="Смена классового умения", cost=5, note=OPENER_NOTE),
    KarmaOpener(name="Смена предыстории", cost=10, note=OPENER_NOTE),
    KarmaOpener(name="Открыть заклинание", cost=5, note=OPENER_NOTE),
    KarmaOpener(name="Смена опционального умения", cost=5, note=OPENER_NOTE),
    KarmaOpener(name="Мультикласс", cost=5, note=OPENER_NOTE),
    KarmaOpener(name="Открыть расу", cost=15, note=OPENER_NOTE),
    KarmaOpener(name="Открыть подкласс", cost=20, note=OPENER_NOTE),
    KarmaOpener(name="Открыть черту", cost=10, note=OPENER_NOTE),
    KarmaOpener(name="Открыть предысторию", cost=10, note=OPENER_NOTE),
)
OPENER_COSTS = {opener.name: opener.cost for opener in OPENER_CATALOG}


def owned_character(character_id: int, user: User, project_id: int, db: Session) -> Character:
    character = db.query(Character).filter(
        Character.id == character_id,
        Character.user_id == user.id,
        Character.project_id == project_id,
    ).first()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    return character


def charge_karma(membership: ProjectMembership, cost: int) -> None:
    if membership.karma < cost:
        raise HTTPException(status_code=400, detail="Недостаточно кармы")
    membership.karma -= cost


def record_purchase(
    db: Session,
    membership: ProjectMembership,
    purchase_type: str,
    name: str,
    cost: int,
    character: Character | None = None,
) -> KarmaPurchase:
    user = membership.user
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
    membership: ProjectMembership,
    purchase: KarmaPurchase,
    character: Character | None = None,
) -> dict:
    db.commit()
    db.refresh(purchase)
    db.refresh(membership)
    if character:
        db.refresh(character)
    return {
        "purchase": purchase,
        "remaining_karma": membership.karma,
        "character_level": character.level if character else None,
        "character_xp": character.xp if character else None,
        "character_is_dead": character.is_dead if character else None,
    }


@router.get("/purchases", response_model=list[KarmaPurchaseResponse])
def list_owned_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    access=Depends(get_current_project_access),
):
    project, _ = access
    return db.query(KarmaPurchase).filter(
        KarmaPurchase.user_id == current_user.id,
        KarmaPurchase.project_id == project.id,
        KarmaPurchase.purchase_type.in_(("item", "opener")),
    ).order_by(KarmaPurchase.created_at.desc(), KarmaPurchase.id.desc()).all()


@router.get("/openers", response_model=list[KarmaOpener])
def list_openers():
    return OPENER_CATALOG


@router.post("/xp", response_model=KarmaPurchaseResult)
def purchase_xp(
    request: KarmaXpPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    access=Depends(get_current_project_access),
):
    project, _ = access
    membership = db.query(ProjectMembership).filter_by(project_id=project.id, user_id=current_user.id).one()
    character = owned_character(request.character_id, current_user, project.id, db)
    cost = request.amount * XP_KARMA_COST
    charge_karma(membership, cost)
    apply_xp_delta(character, request.amount)
    purchase = record_purchase(
        db, membership, "xp", f"{request.amount} опыта", cost, character,
    )
    purchase.project_id = project.id
    return commit_result(db, membership, purchase, character)


@router.post("/purchases", response_model=KarmaPurchaseResult)
def purchase_item(
    request: KarmaItemPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    access=Depends(get_current_project_access),
):
    cost = (
        OPENER_COSTS.get(request.name, request.cost)
        if request.purchase_type == "opener"
        else request.cost
    )
    charge_karma(current_user, cost)
    purchase = record_purchase(
        db, current_user, request.purchase_type, request.name, cost,
    )
    purchase.project_id = project.id
    return commit_result(db, membership, purchase)


@router.post("/resurrect", response_model=KarmaPurchaseResult)
def resurrect_character(
    request: KarmaResurrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    access=Depends(get_current_project_access),
):
    project, _ = access
    membership = db.query(ProjectMembership).filter_by(project_id=project.id, user_id=current_user.id).one()
    character = owned_character(request.character_id, current_user, project.id, db)
    if not character.is_dead:
        raise HTTPException(status_code=400, detail="Персонаж не погиб")
    if character.level >= 11:
        raise HTTPException(
            status_code=400,
            detail="Воскрешение недоступно персонажам 11 уровня и выше",
        )
    cost = 5 if character.level <= 5 else 10
    charge_karma(membership, cost)
    character.is_dead = False
    purchase = record_purchase(
        db, membership, "resurrection", "Воскрешение персонажа", cost, character,
    )
    purchase.project_id = project.id
    return commit_result(db, membership, purchase, character)
