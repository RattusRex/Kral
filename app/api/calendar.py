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

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.users import get_current_user
from app.core import calendar as game_calendar
from app.db.database import SessionLocal
from app.models.character import (
    CalendarAuditLog,
    Character,
    DowntimeEntry,
)
from app.models.user import User
from app.schemas.character import (
    CalendarSummaryResponse,
    DowntimeEntryCreate,
    DowntimeEntryUpdate,
)

router = APIRouter()


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


def charge_character_downtime(
    character: Character,
    db: Session,
    days: int,
    reason: str,
    source: str = "shop",
    current_date: date | None = None,
) -> list[DowntimeEntry]:
    """Spend ``days`` of the character's oldest free days.

    Creates one :class:`DowntimeEntry` per contiguous run of spent days and
    adds them to the session (the caller commits).  Raises a 400
    :class:`HTTPException` when the character does not have enough free days.
    """
    current = current_date or game_calendar.current_game_date()
    try:
        runs = game_calendar.plan_oldest_day_spend(
            character.downtime_entries,
            character.game_created_at,
            current,
            days,
        )
    except ValueError:
        summary = game_calendar.calendar_summary(
            character.downtime_entries,
            character.game_created_at,
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
        )
        db.add(entry)
        entries.append(entry)
    return entries


def build_summary(character: Character, can_manage: bool = False) -> dict:
    summary = game_calendar.calendar_summary(
        character.downtime_entries,
        character.game_created_at,
    )
    summary["can_manage"] = can_manage
    summary["entries"] = sorted(
        character.downtime_entries,
        key=lambda entry: (entry.start_date, entry.id),
    )
    return summary


def validate_downtime_window(
    character: Character,
    start_date: date,
    days: int,
) -> None:
    """Validate a downtime span against the character's active calendar window."""
    if days <= 0:
        raise HTTPException(
            status_code=400,
            detail="Количество дней должно быть больше нуля."
        )

    if start_date < character.game_created_at:
        raise HTTPException(
            status_code=400,
            detail=(
                "Нельзя занять дни раньше даты создания персонажа "
                f"({character.game_created_at.strftime('%d.%m.%Y')})."
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


@router.get(
    "/characters/{character_id}/calendar",
    response_model=CalendarSummaryResponse
)
def get_character_calendar(
    character_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    character = get_character_for_current_user(character_id, current_user, db)
    return build_summary(character, can_manage=current_user.is_admin)


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

    validate_downtime_window(character, entry_data.start_date, entry_data.days)

    entry = DowntimeEntry(
        character_id=character.id,
        start_date=entry_data.start_date,
        days=entry_data.days,
        reason=entry_data.reason,
        source="manual",
    )
    db.add(entry)
    db.flush()

    if current_user.is_admin:
        record_calendar_audit(
            db, current_user, character, "create", entry,
            f"Добавлена запись: {describe_entry(entry)}",
        )

    db.commit()
    db.refresh(character)
    return build_summary(character, can_manage=current_user.is_admin)


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
        DowntimeEntry.character_id == character.id
    ).first()
    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Запись календаря не найдена"
        )

    before = describe_entry(entry)
    new_start = entry_data.start_date if entry_data.start_date is not None else entry.start_date
    new_days = entry_data.days if entry_data.days is not None else entry.days
    validate_downtime_window(character, new_start, new_days)

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
        DowntimeEntry.character_id == character.id
    ).first()
    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Запись календаря не найдена"
        )

    record_calendar_audit(
        db, current_user, character, "delete", entry,
        f"Удалена запись: {describe_entry(entry)}",
    )
    db.delete(entry)
    db.commit()
    db.refresh(character)
    return build_summary(character, can_manage=current_user.is_admin)
