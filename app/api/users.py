from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models.user import User
from app.schemas.user import UserCreate
from app.schemas.user import KarmaUpdate
from fastapi import HTTPException
from app.core.security import (
    verify_password,
    create_access_token
)
from app.schemas.user import UserLogin
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import (
    oauth2_scheme,
    verify_access_token
)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/users")
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "karma": user.karma
    }
@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        (User.email == form_data.username) |
        (User.username == form_data.username)
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not verify_password(
        form_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    access_token = create_access_token(
        data={"sub": user.email}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    email = verify_access_token(token)

    user = db.query(User).filter(
        User.email == email
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user

@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user)
):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "karma": current_user.karma,
        "is_admin": current_user.is_admin
    }

@router.post("/me/karma/add")
def add_karma(
    karma_data: KarmaUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if karma_data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be positive"
        )

    current_user.karma += karma_data.amount
    db.commit()
    db.refresh(current_user)

    return {
        "id": current_user.id,
        "karma": current_user.karma
    }


@router.post("/me/karma/subtract")
def subtract_karma(
    karma_data: KarmaUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if karma_data.amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be positive"
        )

    current_user.karma -= karma_data.amount
    db.commit()
    db.refresh(current_user)

    return {
        "id": current_user.id,
        "karma": current_user.karma
    }
