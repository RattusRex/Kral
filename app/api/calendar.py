"""Game calendar endpoints: per-character free/busy day tracking.

Access rules (see issue #51):

* **Players** may view their own calendar and *add* busy days, but may never
  delete or edit existing entries — the history of spent time is immutable for
  them.
* **Administrators** (admin, head admin, owner) may view, add, edit and delete
  busy days for *any* character in order to correct calendar mistakes.

Every administrative modification (create / update / delete) is recorded in the
:class:`CalendarAuditLog` so corrections can be audited later.
"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.users import get_current_user
from app.core import calendar as game_calendar
from app.db.database import SessionLocal
from app.models.character import (
    CalendarAuditLog,
    Character,
    DowntimeEntry,
)
from app.models.inventory import Inventory, ShopTransactionLog
from app.models.user import User
from app.schemas.character import (
    CalendarSummaryResponse,
    DowntimeEntryCreate,
    DowntimeEntryUpdate,
    WorkEntryCreate,
    WorkEntryResponse,
)

router = APIRouter()

AGENT_CHARACTER = "character"
AGENT_PERSONAL_HIRELING = "personal_hireling"
AGENT_SIMULACRUM = "simulacrum"
CALENDAR_AGENT_LABELS = {
    AGENT_CHARACTER: "Персонаж",
    AGENT_PERSONAL_HIRELING: "Личный наёмник",
    AGENT_SIMULACRUM: "Симулякр",
}
CALENDAR_AGENT_START_LABELS = {
    AGENT_CHARACTER: "даты создания персонажа",
    AGENT_PERSONAL_HIRELING: "даты получения личного наёмника",
    AGENT_SIMULACRUM: "даты создания симулякра",
}
UNIT_AGENT_TYPES = {AGENT_PERSONAL_HIRELING, AGENT_SIMULACRUM}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_character_or_404(character_id: int, db: Session) -> Character:
    """Return any character by id, regardless of ownership."""
    character = db.query(Character).filter(
        Character.id == character_id
    ).first()
    if not character:
        raise HTTPException(
            status_code=404,
            detail="Персонаж не найден"
        )
    return character


def get_character_for_current_user(
    character_id: int,
    current_user: User,
    db: Session
) -> Character:
    """Return a character the current user is allowed to *view* / add days to.

    Owners of the character and any administrator may access it.  Anyone else
    gets a 404 so the existence of other players' characters is not leaked.
    """
    character = db.query(Character).filter(
        Character.id == character_id
    ).first()
    if not character or (
        character.user_id != current_user.id and not current_user.is_admin
    ):
        raise HTTPException(
            status_code=404,
            detail="Персонаж не найден"
        )
    return character


def require_calendar_manager(current_user: User) -> None:
    """Reject non-administrators trying to edit or delete calendar entries."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail=(
                "Игрок не может изменять или удалять занятые дни. "
                "Обратитесь к администратору для корректировки календаря."
            )
        )


def record_calendar_audit(
    db: Session,
    user: User,
    character: Character,
    action: str,
    entry: DowntimeEntry | None,
    details: str,
) -> None:
    """Append a calendar audit-log row for an administrative change."""
    db.add(CalendarAuditLog(
        user_id=user.id,
        username=user.username,
        role=user.role,
        character_id=character.id,
        character_name=character.name,
        action=action,
        entry_id=entry.id if entry is not None else None,
        details=details,
    ))


def describe_entry(entry: DowntimeEntry) -> str:
    return (
        f"{entry.start_date.isoformat()} · {entry.days} дн. "
        f"({entry.reason or 'без описания'})"
    )


def normalize_calendar_agent(agent_type: str) -> str:
    normalized = agent_type.strip().casefold().replace("-", "_")
    if normalized not in CALENDAR_AGENT_LABELS:
        raise HTTPException(
            status_code=400,
            detail="Неизвестный календарный ресурс"
        )
    return normalized


def require_unit_agent(agent_type: str) -> None:
    if agent_type not in UNIT_AGENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Этот маршрут предназначен для личного наёмника или симулякра"
        )


def agent_created_at(character: Character, agent_type: str) -> date:
    if agent_type == AGENT_PERSONAL_HIRELING:
        return character.personal_hireling_acquired_at
    if agent_type == AGENT_SIMULACRUM:
        return character.simulacrum_created_at
    return character.game_created_at


def agent_enabled(character: Character, agent_type: str) -> bool:
    if agent_type == AGENT_PERSONAL_HIRELING:
        return character.personal_hireling_enabled
    if agent_type == AGENT_SIMULACRUM:
        return character.simulacrum_enabled
    return True


def require_agent_available(character: Character, agent_type: str) -> date:
    if not agent_enabled(character, agent_type):
        raise HTTPException(
            status_code=400,
            detail=f"{CALENDAR_AGENT_LABELS[agent_type]} не выдан персонажу"
        )
    return agent_created_at(character, agent_type)


def downtime_for_agent(character: Character, agent_type: str) -> list[DowntimeEntry]:
    return [
        entry
        for entry in character.downtime_entries
        if entry.agent_type == agent_type
    ]


def charge_character_downtime(
    character: Character,
    db: Session,
    days: int,
    reason: str,
    source: str = "shop",
    agent_type: str = "character",
    created_at: date | None = None,
    current_date: date | None = None,
) -> list[DowntimeEntry]:
    """Spend ``days`` of an actor's oldest free days.

    Creates one :class:`DowntimeEntry` per contiguous run of spent days and
    adds them to the session (the caller commits).  Raises a 400
    :class:`HTTPException` when the actor does not have enough free days.
    """
    current = current_date or game_calendar.current_game_date()
    normalized_agent = normalize_calendar_agent(agent_type)
    actor_created_at = created_at or agent_created_at(character, normalized_agent)
    actor_entries = downtime_for_agent(character, normalized_agent)
    try:
        runs = game_calendar.plan_oldest_day_spend(
            actor_entries,
            actor_created_at,
            current,
            days,
        )
    except ValueError:
        summary = game_calendar.calendar_summary(
            actor_entries,
            actor_created_at,
            current,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "Недостаточно свободных дней: требуется "
                f"{days}, доступно {summary['free_days']}."
            )
        )

    entries: list[DowntimeEntry] = []
    for start_date, length in runs:
        entry = DowntimeEntry(
            character_id=character.id,
            start_date=start_date,
            days=length,
            reason=reason,
            source=source,
            agent_type=normalized_agent,
        )
        db.add(entry)
        entries.append(entry)
    return entries


DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def build_summary(
    character: Character,
    can_manage: bool = False,
    agent_type: str = AGENT_CHARACTER,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict:
    normalized_agent = normalize_calendar_agent(agent_type)
    entries = downtime_for_agent(character, normalized_agent)
    summary = game_calendar.calendar_summary(
        entries,
        agent_created_at(character, normalized_agent),
    )
    summary["can_manage"] = can_manage
    sorted_entries = sorted(
        entries,
        key=lambda entry: (entry.start_date, entry.id),
        reverse=True,
    )
    total_entries = len(sorted_entries)
    summary["page"] = page
    summary["page_size"] = page_size
    summary["total_entries"] = total_entries
    summary["pages"] = (total_entries + page_size - 1) // page_size
    start = (page - 1) * page_size
    summary["entries"] = sorted_entries[start:start + page_size]
    return summary


def validate_downtime_window(
    created_at: date,
    start_date: date,
    days: int,
    start_label: str,
) -> None:
    """Validate a downtime span against the character's active calendar window."""
    if days <= 0:
        raise HTTPException(
            status_code=400,
            detail="Количество дней должно быть больше нуля."
        )

    if start_date < created_at:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Нельзя занять дни раньше {start_label} "
                f"({created_at.strftime('%d.%m.%Y')})."
            )
        )

    current = game_calendar.current_game_date()
    if start_date >= current:
        raise HTTPException(
            status_code=400,
            detail="Нельзя занять дни в будущем."
        )

    max_days = (current - start_date).days
    if days > max_days:
        raise HTTPException(
            status_code=400,
            detail=(
                "Запись занятых дней выходит за текущую дату календаря. "
                f"Максимум с выбранной даты: {max_days}."
            )
        )


def validate_no_downtime_overlap(
    entries: list[DowntimeEntry],
    start_date: date,
    days: int,
    excluded_entry_id: int | None = None,
) -> None:
    """Reject a busy span that intersects another entry for the same actor."""
    end_date = start_date + timedelta(days=days)
    for entry in entries:
        if entry.id == excluded_entry_id:
            continue
        entry_end = entry.start_date + timedelta(days=entry.days)
        if start_date < entry_end and entry.start_date < end_date:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Запись занятых дней пересекается с существующей записью "
                    f"({entry.start_date.strftime('%d.%m.%Y')} · {entry.days} дн.)."
                ),
            )


def create_manual_downtime_entry(
    character: Character,
    entry_data: DowntimeEntryCreate,
    db: Session,
    current_user: User,
    agent_type: str = AGENT_CHARACTER,
) -> dict:
    normalized_agent = normalize_calendar_agent(agent_type)
    created_at = require_agent_available(character, normalized_agent)
    validate_downtime_window(
        created_at,
        entry_data.start_date,
        entry_data.days,
        CALENDAR_AGENT_START_LABELS[normalized_agent],
    )
    validate_no_downtime_overlap(
        downtime_for_agent(character, normalized_agent),
        entry_data.start_date,
        entry_data.days,
    )

    entry = DowntimeEntry(
        character_id=character.id,
        start_date=entry_data.start_date,
        days=entry_data.days,
        reason=entry_data.reason,
        source="manual",
        agent_type=normalized_agent,
    )
    db.add(entry)
    db.flush()

    if current_user.is_admin:
        record_calendar_audit(
            db, current_user, character, "create", entry,
            (
                f"{CALENDAR_AGENT_LABELS[normalized_agent]}: "
                f"добавлена запись: {describe_entry(entry)}"
            ),
        )

    db.commit()
    db.refresh(character)
    return build_summary(
        character,
        can_manage=current_user.is_admin,
        agent_type=normalized_agent,
    )


@router.post(
    "/characters/{character_id}/calendar/work",
    response_model=WorkEntryResponse,
)
def create_work_entry(
    character_id: int,
    work: WorkEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reserve a work span, credit its income, and record one finance log."""
    character = get_character_for_current_user(character_id, current_user, db)
    validate_downtime_window(
        character.game_created_at,
        work.start_date,
        work.days,
        CALENDAR_AGENT_START_LABELS[AGENT_CHARACTER],
    )
    validate_no_downtime_overlap(
        downtime_for_agent(character, AGENT_CHARACTER),
        work.start_date,
        work.days,
    )
    income_copper = game_calendar.work_income_copper(
        work.proficiency_modifier,
        work.days,
    )
    entry = DowntimeEntry(
        character_id=character.id,
        start_date=work.start_date,
        days=work.days,
        reason=f"Работа: {work.tools}",
        source="work",
        agent_type=AGENT_CHARACTER,
        tools=work.tools,
        proficiency_modifier=work.proficiency_modifier,
        income_copper=income_copper,
    )
    db.add(entry)
    inventory = character.inventory
    if inventory is None:
        inventory = Inventory(character_id=character.id)
        db.add(inventory)
        db.flush()
    total_copper = (
        inventory.gold * 100 + inventory.silver * 10 + inventory.copper
        + income_copper
    )
    inventory.gold = total_copper // 100
    total_copper %= 100
    inventory.silver = total_copper // 10
    inventory.copper = total_copper % 10
    db.add(ShopTransactionLog(
        user_id=character.owner.id,
        username=character.owner.username,
        character_id=character.id,
        character_name=character.name,
        inventory_id=inventory.id,
        mode="work",
        item_name=work.tools,
        rarity=f"Модификатор {work.proficiency_modifier:+d} · {work.days} дн.",
        item_price=income_copper // 100,
        hireling_cost=0,
        total_amount=income_copper // 100,
        total_copper=income_copper,
    ))
    db.commit()
    db.refresh(entry)
    db.refresh(inventory)
    return {
        "entry": entry,
        "income_copper": income_copper,
        "income": {
            "gold": income_copper // 100,
            "silver": income_copper % 100 // 10,
            "copper": income_copper % 10,
        },
        "inventory": inventory,
    }


@router.get(
    "/characters/{character_id}/calendar",
    response_model=CalendarSummaryResponse
)
def get_character_calendar(
    character_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = get_character_for_current_user(character_id, current_user, db)
    return build_summary(
        character, can_manage=current_user.is_admin, page=page, page_size=page_size
    )


@router.get(
    "/characters/{character_id}/calendar/agents/{agent_type}",
    response_model=CalendarSummaryResponse
)
def get_agent_calendar(
    character_id: int,
    agent_type: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    normalized_agent = normalize_calendar_agent(agent_type)
    require_unit_agent(normalized_agent)
    character = get_character_for_current_user(character_id, current_user, db)
    require_agent_available(character, normalized_agent)
    return build_summary(
        character,
        can_manage=current_user.is_admin,
        agent_type=normalized_agent,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/characters/{character_id}/calendar/downtime",
    response_model=CalendarSummaryResponse
)
def add_downtime_entry(
    character_id: int,
    entry_data: DowntimeEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = get_character_for_current_user(character_id, current_user, db)
    return create_manual_downtime_entry(
        character,
        entry_data,
        db,
        current_user,
    )


@router.post(
    "/characters/{character_id}/calendar/agents/{agent_type}/downtime",
    response_model=CalendarSummaryResponse
)
def add_agent_downtime_entry(
    character_id: int,
    agent_type: str,
    entry_data: DowntimeEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_calendar_manager(current_user)
    normalized_agent = normalize_calendar_agent(agent_type)
    require_unit_agent(normalized_agent)
    character = get_character_or_404(character_id, db)
    return create_manual_downtime_entry(
        character,
        entry_data,
        db,
        current_user,
        agent_type=normalized_agent,
    )


@router.patch(
    "/characters/{character_id}/calendar/downtime/{entry_id}",
    response_model=CalendarSummaryResponse
)
def update_downtime_entry(
    character_id: int,
    entry_id: int,
    entry_data: DowntimeEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_calendar_manager(current_user)
    character = get_character_or_404(character_id, db)
    entry = db.query(DowntimeEntry).filter(
        DowntimeEntry.id == entry_id,
        DowntimeEntry.character_id == character.id,
        DowntimeEntry.agent_type == AGENT_CHARACTER
    ).first()
    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Запись календаря не найдена"
        )
    if entry.source == "work":
        raise HTTPException(
            status_code=409,
            detail="Запись работы нельзя изменить после начисления заработка.",
        )

    before = describe_entry(entry)
    new_start = entry_data.start_date if entry_data.start_date is not None else entry.start_date
    new_days = entry_data.days if entry_data.days is not None else entry.days
    validate_downtime_window(
        character.game_created_at,
        new_start,
        new_days,
        CALENDAR_AGENT_START_LABELS[AGENT_CHARACTER],
    )
    validate_no_downtime_overlap(
        downtime_for_agent(character, AGENT_CHARACTER),
        new_start,
        new_days,
        excluded_entry_id=entry.id,
    )

    entry.start_date = new_start
    entry.days = new_days
    if entry_data.reason is not None:
        entry.reason = entry_data.reason

    record_calendar_audit(
        db, current_user, character, "update", entry,
        f"Изменена запись: {before} → {describe_entry(entry)}",
    )

    db.commit()
    db.refresh(character)
    return build_summary(character, can_manage=current_user.is_admin)


@router.patch(
    "/characters/{character_id}/calendar/agents/{agent_type}/downtime/{entry_id}",
    response_model=CalendarSummaryResponse
)
def update_agent_downtime_entry(
    character_id: int,
    agent_type: str,
    entry_id: int,
    entry_data: DowntimeEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_calendar_manager(current_user)
    normalized_agent = normalize_calendar_agent(agent_type)
    require_unit_agent(normalized_agent)
    character = get_character_or_404(character_id, db)
    created_at = require_agent_available(character, normalized_agent)
    entry = db.query(DowntimeEntry).filter(
        DowntimeEntry.id == entry_id,
        DowntimeEntry.character_id == character.id,
        DowntimeEntry.agent_type == normalized_agent,
    ).first()
    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Запись календаря не найдена"
        )
    before = describe_entry(entry)
    new_start = entry_data.start_date if entry_data.start_date is not None else entry.start_date
    new_days = entry_data.days if entry_data.days is not None else entry.days
    validate_downtime_window(
        created_at,
        new_start,
        new_days,
        CALENDAR_AGENT_START_LABELS[normalized_agent],
    )
    validate_no_downtime_overlap(
        downtime_for_agent(character, normalized_agent),
        new_start,
        new_days,
        excluded_entry_id=entry.id,
    )

    entry.start_date = new_start
    entry.days = new_days
    if entry_data.reason is not None:
        entry.reason = entry_data.reason

    record_calendar_audit(
        db, current_user, character, "update", entry,
        (
            f"{CALENDAR_AGENT_LABELS[normalized_agent]}: "
            f"изменена запись: {before} → {describe_entry(entry)}"
        ),
    )

    db.commit()
    db.refresh(character)
    return build_summary(
        character,
        can_manage=current_user.is_admin,
        agent_type=normalized_agent,
    )


@router.delete(
    "/characters/{character_id}/calendar/downtime/{entry_id}",
    response_model=CalendarSummaryResponse
)
def delete_downtime_entry(
    character_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_calendar_manager(current_user)
    character = get_character_or_404(character_id, db)
    entry = db.query(DowntimeEntry).filter(
        DowntimeEntry.id == entry_id,
        DowntimeEntry.character_id == character.id,
        DowntimeEntry.agent_type == AGENT_CHARACTER
    ).first()
    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Запись календаря не найдена"
        )
    if entry.source == "work":
        raise HTTPException(
            status_code=409,
            detail="Запись работы нельзя удалить после начисления заработка.",
        )

    record_calendar_audit(
        db, current_user, character, "delete", entry,
        f"Удалена запись: {describe_entry(entry)}",
    )
    db.delete(entry)
    db.commit()
    db.refresh(character)
    return build_summary(character, can_manage=current_user.is_admin)


@router.delete(
    "/characters/{character_id}/calendar/agents/{agent_type}/downtime/{entry_id}",
    response_model=CalendarSummaryResponse
)
def delete_agent_downtime_entry(
    character_id: int,
    agent_type: str,
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    require_calendar_manager(current_user)
    normalized_agent = normalize_calendar_agent(agent_type)
    require_unit_agent(normalized_agent)
    character = get_character_or_404(character_id, db)
    require_agent_available(character, normalized_agent)
    entry = db.query(DowntimeEntry).filter(
        DowntimeEntry.id == entry_id,
        DowntimeEntry.character_id == character.id,
        DowntimeEntry.agent_type == normalized_agent,
    ).first()
    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Запись календаря не найдена"
        )

    record_calendar_audit(
        db, current_user, character, "delete", entry,
        (
            f"{CALENDAR_AGENT_LABELS[normalized_agent]}: "
            f"удалена запись: {describe_entry(entry)}"
        ),
    )
    db.delete(entry)
    db.commit()
    db.refresh(character)
    return build_summary(
        character,
        can_manage=current_user.is_admin,
        agent_type=normalized_agent,
    )
