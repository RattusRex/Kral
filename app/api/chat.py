import random
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.users import get_current_user, get_db
from app.api.projects import get_current_project_access, require_feature
from app.models.chat import ChatMessage
from app.models.project import Project, ProjectMembership
from app.models.user import User
from app.core.roles import is_admin_role
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    DiceRollRequest,
)


router = APIRouter(dependencies=[Depends(get_current_project_access)])
ROLL_PATTERN = re.compile(r"^(?P<count>\d*)d(?P<sides>\d+)$", re.IGNORECASE)
VALID_CHANNELS = {"general", "rolls"}
MAX_DICE_COUNT = 100
MAX_DICE_SIDES = 10000


def normalize_roll_command(formula: str) -> str:
    normalized = formula.strip()
    if normalized.lower().startswith("/r"):
        normalized = normalized[2:].strip()
    return normalized.lower()


def roll_dice_formula(formula: str) -> tuple[str, list[int], int]:
    normalized = normalize_roll_command(formula)
    match = ROLL_PATTERN.match(normalized)
    if not match:
        raise HTTPException(
            status_code=400,
            detail="Dice formula must look like /r 2d6"
        )

    count = int(match.group("count") or "1")
    sides = int(match.group("sides"))
    if count < 1 or count > MAX_DICE_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Dice count must be between 1 and {MAX_DICE_COUNT}"
        )
    if sides < 1 or sides > MAX_DICE_SIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Dice sides must be between 1 and {MAX_DICE_SIDES}"
        )

    rolls = [random.randint(1, sides) for _ in range(count)]
    return f"{count}d{sides}", rolls, sum(rolls)


def create_roll_chat_message(
    db: Session,
    user: User,
    formula: str,
    rolls: list[int],
    total: int,
    content: str | None = None,
    project_id: int | None = None,
) -> ChatMessage:
    message = ChatMessage(
        user_id=user.id,
        project_id=project_id,
        username=user.username,
        channel="rolls",
        content=content or (
            f"{user.username}\n"
            f"Бросок: {formula}\n"
            f"Результаты: {rolls}\n"
            f"Итого: {total}"
        ),
        formula=formula,
        rolls=rolls,
        total=total
    )
    db.add(message)
    return message


def require_message_content(content: str) -> str:
    normalized = content.strip()
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="Message must not be empty"
        )
    return normalized


@router.get("/leaderboard")
def get_leaderboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    project: Project = Depends(require_feature("leaderboard")),
):
    rows = db.query(User, ProjectMembership).join(
        ProjectMembership, ProjectMembership.user_id == User.id
    ).filter(
        ProjectMembership.project_id == project.id
    ).order_by(
        ProjectMembership.karma.desc(),
        User.username.asc()
    ).all()
    return [{
        "rank": index + 1,
        "id": user.id,
        "username": user.username,
        "karma": membership.karma
    } for index, (user, membership) in enumerate(rows)]


@router.get("/chat/messages", response_model=list[ChatMessageResponse])
def list_chat_messages(
    channel: str = Query(default="general"),
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    access: tuple[Project, str] = Depends(get_current_project_access),
):
    if channel not in VALID_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail="Unknown chat channel"
        )

    query = db.query(ChatMessage).filter(
        ChatMessage.project_id == access[0].id,
        ChatMessage.channel == channel,
    )
    if before_id is not None:
        query = query.filter(ChatMessage.id < before_id)
    rows = query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc()).limit(limit).all()
    return list(reversed(rows))


@router.post("/chat/messages", response_model=ChatMessageResponse)
def create_chat_message(
    message_data: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    access: tuple[Project, str] = Depends(get_current_project_access),
):
    content = require_message_content(message_data.content)
    if content.lower().startswith("/r"):
        formula, rolls, total = roll_dice_formula(content)
        message = create_roll_chat_message(
            db=db,
            user=current_user,
            formula=formula,
            rolls=rolls,
            total=total,
            project_id=access[0].id,
        )
    else:
        message = ChatMessage(
            user_id=current_user.id,
            project_id=access[0].id,
            username=current_user.username,
            channel="general",
            content=content
        )
        db.add(message)

    db.commit()
    db.refresh(message)
    return message


@router.delete("/chat/messages/{message_id}", status_code=204)
def delete_chat_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    access: tuple[Project, str] = Depends(get_current_project_access),
):
    if access[1] not in ("owner", "project_owner", "head_admin", "admin", "technician"):
        raise HTTPException(status_code=403, detail="Admin permissions required")
    message = db.query(ChatMessage).filter(
        ChatMessage.id == message_id,
        ChatMessage.project_id == access[0].id,
    ).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    db.delete(message)
    db.commit()


@router.post("/dice/roll", response_model=ChatMessageResponse)
def roll_dice(
    roll_data: DiceRollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    access: tuple[Project, str] = Depends(get_current_project_access),
):
    formula, rolls, total = roll_dice_formula(roll_data.formula)
    message = create_roll_chat_message(
        db=db,
        user=current_user,
        formula=formula,
        rolls=rolls,
        total=total,
        project_id=access[0].id,
    )
    db.commit()
    db.refresh(message)
    return message
