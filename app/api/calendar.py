"""Game calendar endpoints: per-character free/busy day tracking."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.users import get_current_user
from app.core import calendar as game_calendar
from app.db.database import SessionLocal
from app.models.character import Character, DowntimeEntry
from app.models.user import User
from app.schemas.character import (
    CalendarSummaryResponse,
    DowntimeEntryCreate,
)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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


def build_summary(character: Character) -> dict:
    summary = game_calendar.calendar_summary(
        character.downtime_entries,
        character.game_created_at,
    )
    summary["entries"] = sorted(
        character.downtime_entries,
        key=lambda entry: (entry.start_date, entry.id),
    )
    return summary


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
    return build_summary(character)


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

    if entry_data.days <= 0:
        raise HTTPException(
            status_code=400,
            detail="Количество дней должно быть больше нуля."
        )

    if entry_data.start_date < character.game_created_at:
        raise HTTPException(
            status_code=400,
            detail=(
                "Нельзя занять дни раньше даты создания персонажа "
                f"({character.game_created_at.strftime('%d.%m.%Y')})."
            )
        )

    current = game_calendar.current_game_date()
    if entry_data.start_date >= current:
        raise HTTPException(
            status_code=400,
            detail="Нельзя занять дни в будущем."
        )

    db.add(DowntimeEntry(
        character_id=character.id,
        start_date=entry_data.start_date,
        days=entry_data.days,
        reason=entry_data.reason,
        source="manual",
    ))
    db.commit()
    db.refresh(character)
    return build_summary(character)


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
    character = get_character_for_current_user(character_id, current_user, db)
    entry = db.query(DowntimeEntry).filter(
        DowntimeEntry.id == entry_id,
        DowntimeEntry.character_id == character.id
    ).first()
    if not entry:
        raise HTTPException(
            status_code=404,
            detail="Запись календаря не найдена"
        )
    db.delete(entry)
    db.commit()
    db.refresh(character)
    return build_summary(character)
