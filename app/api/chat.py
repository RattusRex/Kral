import random
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.users import get_current_user, get_db
from app.models.chat import ChatMessage
from app.models.user import User
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    DiceRollRequest,
)


router = APIRouter()
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
    content: str | None = None
) -> ChatMessage:
    message = ChatMessage(
        user_id=user.id,
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
    _: User = Depends(get_current_user)
):
    users = db.query(User).order_by(
        User.karma.desc(),
        User.username.asc()
    ).all()
    return [{
        "rank": index + 1,
        "id": user.id,
        "username": user.username,
        "karma": user.karma
    } for index, user in enumerate(users)]


@router.get("/chat/messages", response_model=list[ChatMessageResponse])
def list_chat_messages(
    channel: str = Query(default="general"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    if channel not in VALID_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail="Unknown chat channel"
        )

    return db.query(ChatMessage).filter(
        ChatMessage.channel == channel
    ).order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc()).all()


@router.post("/chat/messages", response_model=ChatMessageResponse)
def create_chat_message(
    message_data: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    content = require_message_content(message_data.content)
    if content.lower().startswith("/r"):
        formula, rolls, total = roll_dice_formula(content)
        message = create_roll_chat_message(
            db=db,
            user=current_user,
            formula=formula,
            rolls=rolls,
            total=total
        )
    else:
        message = ChatMessage(
            user_id=current_user.id,
            username=current_user.username,
            channel="general",
            content=content
        )
        db.add(message)

    db.commit()
    db.refresh(message)
    return message


@router.post("/dice/roll", response_model=ChatMessageResponse)
def roll_dice(
    roll_data: DiceRollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    formula, rolls, total = roll_dice_formula(roll_data.formula)
    message = create_roll_chat_message(
        db=db,
        user=current_user,
        formula=formula,
        rolls=rolls,
        total=total
    )
    db.commit()
    db.refresh(message)
    return message
