from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.users import get_current_user, get_db
from app.models.character import Character
from app.models.recruitment import GameApplication, GameRecruitment, RecruitmentMessage
from app.models.user import User
from app.schemas.recruitment import (
    ApplicationCreate,
    ParticipantSelection,
    RecruitmentCreate,
    RecruitmentStatusUpdate,
)


router = APIRouter(prefix="/game-recruitments", tags=["game recruitments"])
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def require_recruitment(db: Session, recruitment_id: int) -> GameRecruitment:
    recruitment = db.query(GameRecruitment).options(
        joinedload(GameRecruitment.author),
        joinedload(GameRecruitment.applications).joinedload(GameApplication.user),
        joinedload(GameRecruitment.applications).joinedload(GameApplication.character),
        joinedload(GameRecruitment.messages),
    ).filter(GameRecruitment.id == recruitment_id).first()
    if not recruitment:
        raise HTTPException(status_code=404, detail="Game recruitment not found")
    return recruitment


def serialize_application(application: GameApplication) -> dict:
    return {
        "id": application.id,
        "user_id": application.user_id,
        "username": application.user.username,
        "character_id": application.character_id,
        "character_name": application.character.name,
        "class_name": application.character.class_name,
        "level": application.character.level,
        "created_at": application.created_at,
        "status": application.status,
    }


def serialize_recruitment(recruitment: GameRecruitment, current_user: User) -> dict:
    own_application = next(
        (row for row in recruitment.applications if row.user_id == current_user.id),
        None,
    )
    return {
        "id": recruitment.id,
        "author_id": recruitment.author_id,
        "author_username": recruitment.author.username,
        "created_at": recruitment.created_at,
        "real_date": recruitment.real_date,
        "game_date": recruitment.game_date,
        "start_time": recruitment.start_time,
        "duration": recruitment.duration,
        "location": recruitment.location,
        "quest": recruitment.quest,
        "notes": recruitment.notes,
        "status": recruitment.status,
        "can_manage": recruitment.author_id == current_user.id or current_user.is_admin,
        "application_status": own_application.status if own_application else "not_applied",
        "applications": [serialize_application(row) for row in recruitment.applications],
        "messages": [
            {"id": row.id, "created_at": row.created_at, "content": row.content}
            for row in recruitment.messages
        ],
    }


@router.get("")
def list_recruitments(
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(GameRecruitment).options(
        joinedload(GameRecruitment.author),
        joinedload(GameRecruitment.applications).joinedload(GameApplication.user),
        joinedload(GameRecruitment.applications).joinedload(GameApplication.character),
        joinedload(GameRecruitment.messages),
    ).order_by(
        case((GameRecruitment.status == "upcoming", 0), else_=1),
        GameRecruitment.real_date.asc(),
        GameRecruitment.start_time.asc(),
        GameRecruitment.id.asc(),
    )
    if page is None and page_size is None:
        return [serialize_recruitment(row, current_user) for row in query.all()]

    resolved_page = page or 1
    resolved_page_size = page_size or DEFAULT_PAGE_SIZE
    total = query.count()
    rows = query.offset((resolved_page - 1) * resolved_page_size).limit(
        resolved_page_size
    ).all()
    return {
        "items": [serialize_recruitment(row, current_user) for row in rows],
        "page": resolved_page,
        "page_size": resolved_page_size,
        "total": total,
        "pages": (total + resolved_page_size - 1) // resolved_page_size,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_recruitment(
    data: RecruitmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Administrator role required")
    recruitment = GameRecruitment(
        author_id=current_user.id,
        real_date=data.real_date,
        game_date=data.game_date,
        start_time=data.start_time,
        duration=data.duration.strip(),
        location=data.location.strip(),
        quest=data.quest.strip(),
        notes=data.notes.strip(),
    )
    db.add(recruitment)
    db.commit()
    return serialize_recruitment(require_recruitment(db, recruitment.id), current_user)


@router.patch("/{recruitment_id}/status")
def update_recruitment_status(
    recruitment_id: int,
    data: RecruitmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recruitment = require_recruitment(db, recruitment_id)
    if recruitment.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Only the recruitment author or an administrator can change status",
        )
    recruitment.status = data.status
    db.commit()
    return serialize_recruitment(require_recruitment(db, recruitment.id), current_user)


@router.delete("/{recruitment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recruitment(
    recruitment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recruitment = require_recruitment(db, recruitment_id)
    if recruitment.author_id != current_user.id and not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Only the recruitment author or an administrator can delete it",
        )
    db.delete(recruitment)
    db.commit()


@router.post("/{recruitment_id}/applications", status_code=status.HTTP_201_CREATED)
def apply_to_recruitment(
    recruitment_id: int,
    data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recruitment = require_recruitment(db, recruitment_id)
    if recruitment.status == "completed":
        raise HTTPException(status_code=409, detail="This game has already been completed")
    character = db.query(Character).filter(Character.id == data.character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="Character not found")
    if character.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Character does not belong to current user")
    if character.is_dead:
        raise HTTPException(status_code=400, detail="A dead character cannot join a game")

    application = GameApplication(
        recruitment_id=recruitment.id,
        user_id=current_user.id,
        character_id=character.id,
    )
    message = RecruitmentMessage(
        recruitment_id=recruitment.id,
        content=(
            f'Игрок #{current_user.username} записался на персонаже "{character.name}".\n\n'
            f"Класс: {character.class_name}\nУровень: {character.level}"
        ),
    )
    db.add_all([application, message])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Player is already registered for this game")
    return serialize_recruitment(require_recruitment(db, recruitment.id), current_user)


@router.post("/{recruitment_id}/participants")
def select_participants(
    recruitment_id: int,
    data: ParticipantSelection,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recruitment = require_recruitment(db, recruitment_id)
    if recruitment.author_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the recruitment author can select participants")

    requested_ids = set(data.application_ids)
    applications = {row.id: row for row in recruitment.applications}
    if requested_ids - applications.keys():
        raise HTTPException(status_code=400, detail="Application does not belong to this recruitment")
    for application in recruitment.applications:
        application.status = "selected" if application.id in requested_ids else "applied"

    selected = [applications[row_id] for row_id in data.application_ids]
    lines = [
        f'- #{row.user.username} — "{row.character.name}", класс: {row.character.class_name}, уровень: {row.character.level}'
        for row in selected
    ]
    db.add(RecruitmentMessage(
        recruitment_id=recruitment.id,
        content="Игроки выбраны:\n\n" + "\n".join(lines),
    ))
    db.commit()
    return serialize_recruitment(require_recruitment(db, recruitment.id), current_user)
