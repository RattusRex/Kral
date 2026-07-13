from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.inventory import add_currency, get_character_inventory, validate_rarity
from app.api.users import get_current_user, get_db
from app.models.character import CalendarAuditLog, Character
from app.models.chat import ChatMessage
from app.models.inventory import AdminGrantLog, InventoryItem, KarmaPurchase, MarketSaleLog, ShopTransactionLog, TransferLog
from app.models.user import User
from app.schemas.character import (
    MAX_CHARACTER_LEVEL,
    MIN_CHARACTER_LEVEL,
    CalendarAuditLogResponse,
    CharacterUpdate,
)
from app.schemas.inventory import (
    AdminAddItemRequest,
    AdminCurrencyUpdateRequest,
    AdminGrantLogResponse,
    InventoryResponse,
    MarketSaleLogResponse,
    ShopTransactionLogResponse,
    TransferLogResponse,
)
from app.schemas.user import AdminResourceUpdate, RoleUpdate
from app.schemas.karma_shop import KarmaPurchaseResponse
from app.core import calendar as game_calendar
from app.core.calendar import GAME_EPOCH
from app.core.roles import PROJECT_ROLES, ROLE_RANK, Role, normalize_role
from app.api.projects import get_current_project_access, require_feature, require_project_admin as require_selected_project_admin
from app.core.projects import get_admin_character_or_404
from app.models.project import Project, ProjectMembership
from app.models.recruitment import GameApplication, GameRecruitment, RecruitmentMessage


router = APIRouter(prefix="/admin")
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def paginated_response(query, page: int, page_size: int, serializer) -> dict:
    total = query.count()
    items = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [serializer(item) for item in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
    }


def require_admin(
    current_user: User = Depends(get_current_user),
    access: tuple[Project, str] = Depends(require_selected_project_admin),
) -> User:
    current_user.active_project_id = access[0].id
    current_user.active_project_role = access[1]
    return current_user


@router.get("/karma-shop-logs", response_model=list[KarmaPurchaseResponse])
def list_karma_shop_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    __: Project = Depends(require_feature("karma_logs")),
):
    return db.query(KarmaPurchase).filter(
        KarmaPurchase.project_id == _.active_project_id
    ).order_by(
        KarmaPurchase.created_at.desc(), KarmaPurchase.id.desc()
    ).all()


def require_owner(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_owner:
        raise HTTPException(
            status_code=403,
            detail="Owner permissions required"
        )
    return current_user


def require_role_manager(
    current_user: User = Depends(get_current_user),
    access: tuple[Project, str] = Depends(get_current_project_access),
) -> User:
    """Allow project owners and head administrators to manage project roles."""
    current_user.active_project_id = access[0].id
    current_user.active_project_role = access[1]
    if not current_user.is_owner and access[1] not in (Role.PROJECT_OWNER, Role.HEAD_ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Role management permissions required"
        )
    return current_user


def require_character_deleter(
    current_user: User = Depends(get_current_user),
    access: tuple[Project, str] = Depends(get_current_project_access),
) -> User:
    current_user.active_project_id = access[0].id
    current_user.active_project_role = access[1]
    role = getattr(current_user, "active_project_role", current_user.role)
    if normalize_role(role) not in (Role.OWNER, Role.PROJECT_OWNER, Role.HEAD_ADMIN):
        raise HTTPException(
            status_code=403,
            detail="Only the owner or head administrator may delete characters"
        )
    return current_user


def get_character_or_404(character_id: int, db: Session, user: User) -> Character:
    return get_admin_character_or_404(db, user, character_id)


def add_grant_log(
    db: Session,
    admin: User,
    user: User,
    operation_type: str,
    value: str,
    reason: str,
    character: Character | None = None,
) -> None:
    db.add(AdminGrantLog(
        project_id=character.project_id if character else admin.active_project_id,
        admin_id=admin.id,
        admin_username=admin.username,
        user_id=user.id,
        username=user.username,
        character_id=character.id if character else None,
        character_name=character.name if character else None,
        operation_type=operation_type,
        value=value,
        reason=reason.strip(),
    ))


def downtime_for_agent(character: Character, agent_type: str):
    return [
        entry
        for entry in character.downtime_entries
        if entry.agent_type == agent_type
    ]


def agent_calendar_summary(
    character: Character,
    agent_type: str,
    created_at: date,
    enabled: bool = True,
) -> dict:
    if not enabled:
        return {"total_days": 0, "busy_days": 0, "free_days": 0}
    return game_calendar.calendar_summary(
        downtime_for_agent(character, agent_type),
        created_at,
    )


def serialize_user(user: User, membership: ProjectMembership | None = None) -> dict:
    role = Role.OWNER if user.is_owner else membership.role if membership else user.role
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "karma": membership.karma if membership else user.karma,
        "role": role,
        "is_admin": ROLE_RANK.get(role, 0) >= ROLE_RANK[Role.TECHNICIAN],
        "is_owner": user.is_owner,
        "is_head_admin": role == Role.HEAD_ADMIN,
        "email_verified": user.email_verified,
        "email_verified_at": user.email_verified_at,
    }


def serialize_admin_user(user: User, membership: ProjectMembership | None = None, character_count: int | None = None) -> dict:
    return {
        **serialize_user(user, membership),
        "character_count": character_count if character_count is not None else len(user.characters),
    }


def serialize_character(character: Character):
    character_calendar = agent_calendar_summary(
        character,
        "character",
        character.game_created_at,
    )
    personal_hireling_calendar = agent_calendar_summary(
        character,
        "personal_hireling",
        character.personal_hireling_acquired_at,
        character.personal_hireling_enabled,
    )
    simulacrum_calendar = agent_calendar_summary(
        character,
        "simulacrum",
        character.simulacrum_created_at,
        character.simulacrum_enabled,
    )

    return {
        "id": character.id,
        "name": character.name,
        "class_name": character.class_name,
        "class_levels": character.class_levels or [
            {"class_name": character.class_name, "level": character.level}
        ],
        "subclass": character.subclass,
        "race": character.race,
        "background": character.background,
        "route": character.route,
        "level": character.level,
        "xp": character.xp,
        "hp": character.hp,
        "temp_hp": character.temp_hp,
        "armor_class": character.armor_class,
        "speed": character.speed,
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
        "game_created_at": character.game_created_at,
        "total_days": character_calendar["total_days"],
        "busy_days": character_calendar["busy_days"],
        "free_days": character_calendar["free_days"],
        "personal_hireling_enabled": character.personal_hireling_enabled,
        "personal_hireling_acquired_at": character.personal_hireling_acquired_at,
        "personal_hireling_investigation": character.personal_hireling_investigation,
        "personal_hireling_total_days": personal_hireling_calendar["total_days"],
        "personal_hireling_busy_days": personal_hireling_calendar["busy_days"],
        "personal_hireling_free_days": personal_hireling_calendar["free_days"],
        "simulacrum_enabled": character.simulacrum_enabled,
        "simulacrum_created_at": character.simulacrum_created_at,
        "simulacrum_investigation": character.simulacrum_investigation,
        "simulacrum_total_days": simulacrum_calendar["total_days"],
        "simulacrum_busy_days": simulacrum_calendar["busy_days"],
        "simulacrum_free_days": simulacrum_calendar["free_days"],
        "is_dead": character.is_dead,
        "user_id": character.user_id,
        "owner_username": character.owner.username,
        "owner_email": character.owner.email
    }


def apply_xp_delta(character: Character, amount: int):
    character.level = min(
        MAX_CHARACTER_LEVEL,
        max(MIN_CHARACTER_LEVEL, character.level),
    )
    previous_level = character.level
    character.xp = max(0, character.xp + amount)
    if amount <= 0:
        return

    while (
        character.level < MAX_CHARACTER_LEVEL
        and character.xp >= character.level + 1
    ):
        character.xp -= character.level + 1
        character.level += 1
    gained_levels = character.level - previous_level
    if character.class_levels and gained_levels > 0:
        character.class_levels[-1] = {
            **character.class_levels[-1],
            "level": character.class_levels[-1]["level"] + gained_levels,
        }


def validate_admin_character_update(update_data: dict) -> None:
    date_fields = {
        "game_created_at": "Дата появления персонажа",
        "personal_hireling_acquired_at": "Дата появления личного наёмника",
        "simulacrum_created_at": "Дата появления симулякра",
    }
    for field, label in date_fields.items():
        if field not in update_data:
            continue
        value = update_data[field]
        if value is None:
            update_data[field] = GAME_EPOCH
            value = GAME_EPOCH
        if value < GAME_EPOCH:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{label} не может быть раньше начала игры "
                    f"({GAME_EPOCH.strftime('%d.%m.%Y')})."
                )
            )


@router.get("/characters")
def list_characters(
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    query = db.query(Character).filter(
        Character.project_id == current_user.active_project_id
    ).order_by(Character.id)
    if page is None and page_size is None:
        return [serialize_character(character) for character in query.all()]
    resolved_page = page or 1
    resolved_page_size = page_size or DEFAULT_PAGE_SIZE
    return paginated_response(
        query,
        resolved_page,
        resolved_page_size,
        serialize_character,
    )


@router.get("/characters/{character_id}")
def get_admin_character(
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    return serialize_character(get_character_or_404(character_id, db, current_user))


@router.patch("/characters/{character_id}")
def update_admin_character(
    character_id: int,
    character_data: CharacterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db, current_user)
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

    if "level" in update_data and update_data["level"] is not None:
        update_data["level"] = min(
            MAX_CHARACTER_LEVEL,
            max(MIN_CHARACTER_LEVEL, update_data["level"]),
        )
        if "class_levels" not in update_data and character.class_levels:
            level_delta = update_data["level"] - character.level
            if level_delta:
                adjusted_level = character.class_levels[-1]["level"] + level_delta
                if adjusted_level < MIN_CHARACTER_LEVEL:
                    raise HTTPException(
                        status_code=400,
                        detail="Уровни классов должны быть не меньше 1",
                    )
                update_data["class_levels"] = [
                    *character.class_levels[:-1],
                    {**character.class_levels[-1], "level": adjusted_level},
                ]
    if "xp" in update_data and update_data["xp"] is not None:
        update_data["xp"] = max(0, update_data["xp"])
    validate_admin_character_update(update_data)

    for key, value in update_data.items():
        setattr(character, key, value)

    db.commit()
    db.refresh(character)
    return serialize_character(character)


@router.get("/characters/{character_id}/inventory", response_model=InventoryResponse)
def get_admin_character_inventory(
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db, current_user)
    return get_character_inventory(character.id, character.owner, db)


@router.get("/users")
def list_users(
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    query = db.query(User, ProjectMembership).join(ProjectMembership).filter(
        ProjectMembership.project_id == _.active_project_id
    ).order_by(User.id)
    if page is None and page_size is None:
        return [serialize_admin_user(
            user, membership,
            sum(character.project_id == _.active_project_id for character in user.characters),
        ) for user, membership in query.all()]
    resolved_page = page or 1
    resolved_page_size = page_size or DEFAULT_PAGE_SIZE
    return paginated_response(
        query,
        resolved_page,
        resolved_page_size,
        lambda row: serialize_admin_user(
            row[0], row[1],
            sum(character.project_id == _.active_project_id for character in row[0].characters),
        ),
    )


@router.post("/users/{user_id}/verify-email")
def manually_verify_user_email(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.user_id == user_id,
        ProjectMembership.project_id == _.active_project_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="User not found")
    user = membership.user

    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = datetime.now().astimezone()
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    db.commit()
    db.refresh(user)
    return serialize_admin_user(user, membership)


@router.post("/characters/{character_id}/xp")
def add_character_xp(
    character_id: int,
    xp_data: AdminResourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db, current_user)
    apply_xp_delta(character, xp_data.amount)
    add_grant_log(
        db, current_user, character.owner, "xp",
        f"{xp_data.amount:+d}", xp_data.reason, character,
    )
    db.commit()
    db.refresh(character)
    return character


@router.post("/characters/{character_id}/gold", response_model=InventoryResponse)
def add_character_gold(
    character_id: int,
    gold_data: AdminResourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db, current_user)
    inventory = get_character_inventory(character.id, character.owner, db)
    inventory.gold = max(0, inventory.gold + gold_data.amount)
    add_grant_log(
        db, current_user, character.owner, "gold",
        f"{gold_data.amount:+d}", gold_data.reason, character,
    )
    db.commit()
    db.refresh(inventory)
    return inventory


@router.post("/characters/{character_id}/currency/add", response_model=InventoryResponse)
def add_character_currency(
    character_id: int,
    currency_data: AdminCurrencyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db, current_user)
    inventory = get_character_inventory(character.id, character.owner, db)
    add_currency(
        inventory,
        currency_data.gold,
        currency_data.silver,
        currency_data.copper
    )
    value = (
        f"{currency_data.gold:+d} зм / {currency_data.silver:+d} см / "
        f"{currency_data.copper:+d} мм"
    )
    add_grant_log(
        db, current_user, character.owner, "gold",
        value, currency_data.reason, character,
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
    _: User = Depends(require_admin),
    __: Project = Depends(require_feature("logs")),
):
    query = db.query(ShopTransactionLog).filter(ShopTransactionLog.project_id == _.active_project_id)

    if character_id is not None:
        query = query.filter(ShopTransactionLog.character_id == character_id)
    if user_id is not None:
        query = query.filter(ShopTransactionLog.user_id == user_id)
    if mode:
        if mode not in {"buy", "sell", "work"}:
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


@router.get("/market-sales", response_model=list[MarketSaleLogResponse])
def list_market_sales(
    character_id: int | None = None,
    user_id: int | None = None,
    operation_date: date | None = Query(default=None, alias="date"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    __: Project = Depends(require_feature("market_logs")),
):
    query = db.query(MarketSaleLog).filter(MarketSaleLog.project_id == _.active_project_id)
    if character_id is not None:
        query = query.filter(MarketSaleLog.character_id == character_id)
    if user_id is not None:
        query = query.filter(MarketSaleLog.user_id == user_id)
    if operation_date is not None:
        start = datetime.combine(operation_date, time.min)
        query = query.filter(
            MarketSaleLog.created_at >= start,
            MarketSaleLog.created_at < start + timedelta(days=1),
        )
    else:
        if date_from is not None:
            query = query.filter(
                MarketSaleLog.created_at >= datetime.combine(date_from, time.min)
            )
        if date_to is not None:
            query = query.filter(
                MarketSaleLog.created_at
                < datetime.combine(date_to, time.min) + timedelta(days=1)
            )
    return query.order_by(MarketSaleLog.created_at.desc(), MarketSaleLog.id.desc()).all()


@router.get("/transfer-logs", response_model=list[TransferLogResponse])
def list_transfer_logs(
    character_id: int | None = None,
    user_id: int | None = None,
    transfer_type: str | None = None,
    operation_date: date | None = Query(default=None, alias="date"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    __: Project = Depends(require_feature("logs")),
):
    query = db.query(TransferLog).filter(TransferLog.project_id == _.active_project_id)

    if character_id is not None:
        query = query.filter(
            (TransferLog.sender_character_id == character_id)
            | (TransferLog.recipient_character_id == character_id)
        )
    if user_id is not None:
        query = query.filter(TransferLog.user_id == user_id)
    if transfer_type:
        if transfer_type not in {"currency", "item"}:
            raise HTTPException(
                status_code=400,
                detail="Unknown transfer type"
            )
        query = query.filter(TransferLog.transfer_type == transfer_type)

    if operation_date is not None:
        start = datetime.combine(operation_date, time.min)
        end = start + timedelta(days=1)
        query = query.filter(
            TransferLog.created_at >= start,
            TransferLog.created_at < end
        )
    else:
        if date_from is not None:
            query = query.filter(
                TransferLog.created_at >= datetime.combine(date_from, time.min)
            )
        if date_to is not None:
            query = query.filter(
                TransferLog.created_at < (
                    datetime.combine(date_to, time.min) + timedelta(days=1)
                )
            )

    return query.order_by(TransferLog.created_at.desc()).all()


@router.get("/calendar-logs", response_model=list[CalendarAuditLogResponse])
def list_calendar_logs(
    character_id: int | None = None,
    user_id: int | None = None,
    action: str | None = None,
    operation_date: date | None = Query(default=None, alias="date"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    __: Project = Depends(require_feature("logs")),
):
    """Return the audit trail of administrative calendar changes."""
    query = db.query(CalendarAuditLog).filter(CalendarAuditLog.project_id == _.active_project_id)

    if character_id is not None:
        query = query.filter(CalendarAuditLog.character_id == character_id)
    if user_id is not None:
        query = query.filter(CalendarAuditLog.user_id == user_id)
    if action:
        if action not in {"create", "update", "delete"}:
            raise HTTPException(
                status_code=400,
                detail="Unknown calendar action type"
            )
        query = query.filter(CalendarAuditLog.action == action)

    if operation_date is not None:
        start = datetime.combine(operation_date, time.min)
        end = start + timedelta(days=1)
        query = query.filter(
            CalendarAuditLog.created_at >= start,
            CalendarAuditLog.created_at < end
        )
    else:
        if date_from is not None:
            query = query.filter(
                CalendarAuditLog.created_at >= datetime.combine(date_from, time.min)
            )
        if date_to is not None:
            query = query.filter(
                CalendarAuditLog.created_at < (
                    datetime.combine(date_to, time.min) + timedelta(days=1)
                )
            )

    return query.order_by(CalendarAuditLog.created_at.desc()).all()


@router.get("/grant-logs", response_model=list[AdminGrantLogResponse])
def list_grant_logs(
    character_id: int | None = None,
    user_id: int | None = None,
    admin_id: int | None = None,
    operation_type: str | None = None,
    operation_date: date | None = Query(default=None, alias="date"),
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    __: Project = Depends(require_feature("logs")),
):
    query = db.query(AdminGrantLog).filter(AdminGrantLog.project_id == _.active_project_id)
    if character_id is not None:
        query = query.filter(AdminGrantLog.character_id == character_id)
    if user_id is not None:
        query = query.filter(AdminGrantLog.user_id == user_id)
    if admin_id is not None:
        query = query.filter(AdminGrantLog.admin_id == admin_id)
    if operation_type:
        if operation_type not in {"karma", "xp", "gold", "item"}:
            raise HTTPException(status_code=400, detail="Unknown grant operation type")
        query = query.filter(AdminGrantLog.operation_type == operation_type)
    if operation_date is not None:
        start = datetime.combine(operation_date, time.min)
        query = query.filter(
            AdminGrantLog.created_at >= start,
            AdminGrantLog.created_at < start + timedelta(days=1),
        )
    else:
        if date_from is not None:
            query = query.filter(
                AdminGrantLog.created_at >= datetime.combine(date_from, time.min)
            )
        if date_to is not None:
            query = query.filter(
                AdminGrantLog.created_at
                < datetime.combine(date_to, time.min) + timedelta(days=1)
            )
    return query.order_by(AdminGrantLog.created_at.desc(), AdminGrantLog.id.desc()).all()


@router.post("/characters/{character_id}/revive")
def revive_character(
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    character = get_character_or_404(character_id, db, current_user)
    character.hp = max(character.hp, 1)
    character.is_dead = False
    db.commit()
    db.refresh(character)
    return character


@router.delete("/characters/{character_id}")
def delete_admin_character(
    character_id: int,
    confirmation: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_character_deleter)
):
    if confirmation != "УДАЛИТЬ":
        raise HTTPException(
            status_code=400,
            detail="Введите УДАЛИТЬ для подтверждения удаления"
        )

    character = get_character_or_404(character_id, db, current_user)
    inventory_id = character.inventory.id if character.inventory else None
    if inventory_id is not None:
        # Completed shop logs hold non-null foreign keys to both records.
        # Remove them explicitly so SQLAlchemy does not try to null those keys.
        db.query(ShopTransactionLog).filter(
            (ShopTransactionLog.character_id == character.id)
            | (ShopTransactionLog.inventory_id == inventory_id)
        ).delete(synchronize_session=False)
    db.delete(character)
    db.commit()
    return {"deleted": True, "id": character_id}


@router.post("/characters/{character_id}/item", response_model=InventoryResponse)
def grant_character_item(
    character_id: int,
    item_data: AdminAddItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    validate_rarity(item_data.rarity)
    character = get_character_or_404(character_id, db, current_user)
    inventory = get_character_inventory(character.id, character.owner, db)
    db.add(InventoryItem(
        name=item_data.name,
        rarity=item_data.rarity,
        is_consumable=item_data.is_consumable,
        inventory_id=inventory.id
    ))
    consumable = "расходуемый" if item_data.is_consumable else "постоянный"
    add_grant_log(
        db, current_user, character.owner, "item",
        f"{item_data.name} · {item_data.rarity} · {consumable}",
        item_data.reason, character,
    )
    db.commit()
    db.refresh(inventory)
    return inventory


def update_user_karma(
    user_id: int,
    amount: int,
    reason: str,
    admin: User,
    db: Session,
):
    membership = db.query(ProjectMembership).filter(
        ProjectMembership.user_id == user_id,
        ProjectMembership.project_id == admin.active_project_id,
    ).first()
    if not membership:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    user = membership.user
    membership.karma = max(0, membership.karma + amount)
    add_grant_log(db, admin, user, "karma", f"{amount:+d}", reason)
    db.commit()
    db.refresh(membership)
    return serialize_user(user, membership)


@router.post("/users/{user_id}/role")
def change_user_role(
    user_id: int,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role_manager)
):
    requested_role = normalize_role(role_data.role)
    if role_data.role.strip().lower() == Role.OWNER and not current_user.is_owner:
        raise HTTPException(status_code=403, detail="Only the global owner may assign owners")
    if role_data.role.strip().lower() not in PROJECT_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Role must be one of: {', '.join(PROJECT_ROLES)}"
        )

    membership = db.query(ProjectMembership).filter_by(
        project_id=current_user.active_project_id,
        user_id=user_id,
    ).first()
    if not membership:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    user = membership.user

    if user.is_owner and not current_user.is_owner:
        raise HTTPException(status_code=403, detail="Only the global owner may manage owners")

    if user.id == current_user.id:
        if current_user.is_owner or membership.role == Role.PROJECT_OWNER:
            raise HTTPException(
                status_code=400,
                detail="Project owners cannot demote themselves"
            )
    actor_role = getattr(current_user, "active_project_role", Role.PLAYER)
    if not current_user.is_owner:
        if membership.role == Role.PROJECT_OWNER:
            raise HTTPException(status_code=403, detail="Only the global owner may manage project owners")
        if ROLE_RANK[requested_role] >= ROLE_RANK[actor_role]:
            raise HTTPException(status_code=403, detail="Cannot assign an equal or higher role")
        if ROLE_RANK[membership.role] >= ROLE_RANK[actor_role]:
            raise HTTPException(status_code=403, detail="Cannot manage an equal or higher role")

    membership.role = requested_role
    db.commit()
    db.refresh(membership)
    return serialize_user(user, membership)


@router.delete("/users/{user_id}")
def delete_user_account(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Нельзя удалить собственную учётную запись",
        )
    if user.is_owner and db.query(User).filter(User.role == Role.OWNER).count() <= 1:
        raise HTTPException(
            status_code=409,
            detail="В системе должен остаться хотя бы один владелец",
        )
    if db.query(Project).filter(Project.owner_id == user.id).first():
        raise HTTPException(
            status_code=409,
            detail="Перед удалением передайте принадлежащие пользователю проекты другому владельцу",
        )

    character_ids = [row[0] for row in db.query(Character.id).filter(Character.user_id == user.id)]
    characters = []
    if character_ids:
        db.query(CalendarAuditLog).filter(
            CalendarAuditLog.character_id.in_(character_ids)
        ).delete(synchronize_session=False)
        db.query(ShopTransactionLog).filter(
            ShopTransactionLog.character_id.in_(character_ids)
        ).delete(synchronize_session=False)
        characters = db.query(Character).filter(Character.id.in_(character_ids)).all()

    authored_recruitments = db.query(GameRecruitment).filter(
        GameRecruitment.author_id == user.id
    ).all()
    for recruitment in authored_recruitments:
        db.delete(recruitment)
    db.query(GameApplication).filter(GameApplication.user_id == user.id).delete(synchronize_session=False)
    db.query(RecruitmentMessage).filter(RecruitmentMessage.user_id == user.id).delete(synchronize_session=False)
    db.query(ChatMessage).filter(ChatMessage.user_id == user.id).delete(synchronize_session=False)
    db.query(CalendarAuditLog).filter(CalendarAuditLog.user_id == user.id).delete(synchronize_session=False)
    db.query(ShopTransactionLog).filter(ShopTransactionLog.user_id == user.id).delete(synchronize_session=False)
    db.query(TransferLog).filter(TransferLog.user_id == user.id).delete(synchronize_session=False)
    db.query(ProjectMembership).filter(ProjectMembership.user_id == user.id).delete(synchronize_session=False)
    for character in characters:
        db.delete(character)
    db.delete(user)
    db.commit()
    return {"deleted": True, "id": user_id}


@router.post("/users/{user_id}/karma")
def change_user_karma(
    user_id: int,
    karma_data: AdminResourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    _: Project = Depends(require_feature("karma")),
):
    return update_user_karma(user_id, karma_data.amount, karma_data.reason, current_user, db)


@router.post("/users/{user_id}/karma/add")
def add_user_karma(
    user_id: int,
    karma_data: AdminResourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    _: Project = Depends(require_feature("karma")),
):
    return update_user_karma(user_id, karma_data.amount, karma_data.reason, current_user, db)


@router.post("/users/{user_id}/karma/subtract")
def subtract_user_karma(
    user_id: int,
    karma_data: AdminResourceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
    _: Project = Depends(require_feature("karma")),
):
    if karma_data.amount < 0:
        return update_user_karma(user_id, karma_data.amount, karma_data.reason, current_user, db)
    return update_user_karma(user_id, -karma_data.amount, karma_data.reason, current_user, db)
