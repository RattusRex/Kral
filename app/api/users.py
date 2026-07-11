import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.auth_abuse import (
    assert_login_allowed,
    assert_registration_allowed,
    record_failed_login,
    record_successful_login,
    reject_oversized_password,
)
from app.db.database import SessionLocal
from app.models.user import User
from app.schemas.user import EmailResendRequest, EmailVerificationRequest, UserCreate
from app.core.email_verification import (
    generate_verification_token,
    hash_verification_token,
    send_verification_email,
)
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import (
    oauth2_scheme,
    verify_access_token
)

logger = logging.getLogger(__name__)

router = APIRouter()
VERIFICATION_TOKEN_LIFETIME = timedelta(hours=24)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def issue_verification_token(user: User) -> str:
    token = generate_verification_token()
    user.email_verification_token_hash = hash_verification_token(token)
    user.email_verification_expires_at = datetime.now(timezone.utc) + VERIFICATION_TOKEN_LIFETIME
    return token


@router.post("/users")
def create_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    reject_oversized_password(user_data.password)
    assert_registration_allowed(request)

    normalized_email = user_data.email.lower()

    existing_username = db.query(User).filter(
        User.username == user_data.username
    ).first()
    if existing_username:
        logger.warning("Registration conflict: username %r already exists", user_data.username)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken"
        )

    existing_email = db.query(User).filter(
        func.lower(User.email) == normalized_email
    ).first()
    if existing_email:
        logger.warning("Registration conflict: email %r already exists", normalized_email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    user = User(
        username=user_data.username,
        email=normalized_email,
        hashed_password=hash_password(user_data.password),
        email_verified=False,
    )
    token = issue_verification_token(user)

    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.warning(
            "Registration integrity error for username=%r email=%r",
            user_data.username,
            normalized_email,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists"
        )
    db.refresh(user)

    try:
        send_verification_email(user.email, user.username, token)
    except Exception:
        logger.exception("Failed to send verification email to %s", user.email)
        raise HTTPException(
            status_code=503,
            detail="Account created, but verification email could not be sent",
        )

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "karma": user.karma,
        "email_verified": user.email_verified,
        "message": "Verification email sent",
    }


@router.post("/email/verify")
def verify_email(data: EmailVerificationRequest, db: Session = Depends(get_db)):
    token_hash = hash_verification_token(data.token)
    user = db.query(User).filter(
        User.email_verification_token_hash == token_hash
    ).first()
    now = datetime.now(timezone.utc)
    if not user or not user.email_verification_expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    expires_at = user.email_verification_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    user.email_verified = True
    user.email_verified_at = now
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    db.commit()
    return {"message": "Email verified", "email_verified": True}


@router.post("/email/resend")
def resend_verification_email(data: EmailResendRequest, db: Session = Depends(get_db)):
    normalized_email = data.email.lower()
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    generic_response = {"message": "If the account is awaiting verification, a new email was sent"}
    if not user or user.email_verified:
        return generic_response

    token = issue_verification_token(user)
    db.commit()
    try:
        send_verification_email(user.email, user.username, token)
    except Exception:
        logger.exception("Failed to resend verification email to %s", user.email)
        raise HTTPException(status_code=503, detail="Verification email could not be sent")
    return generic_response


@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    reject_oversized_password(form_data.password)
    assert_login_allowed(request, form_data.username)

    user = db.query(User).filter(
        (func.lower(User.email) == form_data.username.lower()) |
        (User.username == form_data.username)
    ).first()

    if not user:
        record_failed_login(request, form_data.username)
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not verify_password(
        form_data.password,
        user.hashed_password
    ):
        record_failed_login(request, form_data.username)
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not user.email_verified:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "email_not_verified",
                "message": "Для входа необходимо подтвердить адрес электронной почты.",
                "email": user.email,
            },
        )

    record_successful_login(request, form_data.username)

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
        "role": current_user.role,
        "is_admin": current_user.is_admin,
        "is_owner": current_user.is_owner,
        "is_head_admin": current_user.is_head_admin,
        "email_verified": current_user.email_verified,
        "email_verified_at": current_user.email_verified_at,
    }
