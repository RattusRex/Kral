import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.auth_abuse import (
    assert_login_allowed,
    assert_password_reset_allowed,
    assert_registration_allowed,
    record_failed_login,
    record_successful_login,
    reject_oversized_password,
)
from app.db.database import SessionLocal
from app.models.user import User
from app.models.project import DEFAULT_PROJECT_NAME, Project, ProjectMembership
from app.core.passwords import new_password_policy_error
from app.core.roles import Role, is_admin_role
from app.schemas.user import (
    EmailResendRequest,
    EmailVerificationRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    UserCreate,
)
from app.core.email_verification import (
    generate_verification_token,
    hash_verification_token,
    send_password_reset_email,
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
VERIFICATION_DELIVERY_ERROR = (
    "Аккаунт создан, но не удалось отправить письмо подтверждения. "
    "Попробуйте позже или запросите повторную отправку письма."
)

router = APIRouter()
VERIFICATION_TOKEN_LIFETIME = timedelta(hours=24)
PASSWORD_RESET_TOKEN_LIFETIME = timedelta(hours=24)
PASSWORD_RESET_REQUEST_MESSAGE = (
    "Если аккаунт с указанным адресом существует, письмо для восстановления "
    "пароля было отправлено."
)
INVALID_PASSWORD_RESET_LINK = "Ссылка восстановления недействительна или истекла"


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


def issue_password_reset_token(user: User) -> str:
    token = generate_verification_token()
    user.password_reset_token_hash = hash_verification_token(token)
    user.password_reset_expires_at = datetime.now(timezone.utc) + PASSWORD_RESET_TOKEN_LIFETIME
    return token


@router.post("/users")
def create_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    reject_oversized_password(user_data.password)
    password_policy_error = new_password_policy_error(user_data.password)
    if password_policy_error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=password_policy_error,
        )
    assert_registration_allowed(request)

    normalized_email = user_data.email.lower()

    existing_username = db.query(User).filter(
        User.username == user_data.username
    ).first()
    if existing_username:
        logger.warning("Registration conflict: username %r already exists", user_data.username)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Имя пользователя уже занято"
        )

    existing_email = db.query(User).filter(
        func.lower(User.email) == normalized_email
    ).first()
    if existing_email:
        logger.warning("Registration conflict: email %r already exists", normalized_email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот адрес электронной почты уже зарегистрирован"
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
            detail="Имя пользователя или адрес электронной почты уже зарегистрированы"
        )
    db.refresh(user)

    # Registration starts with an explicit ecosystem choice in the UI. Until
    # that choice is submitted, retain compatibility by granting access to the
    # original public campaign; owners may later add/remove project access.
    default_project = db.query(Project).filter(Project.name == DEFAULT_PROJECT_NAME).first()
    if default_project:
        db.add(ProjectMembership(
            project_id=default_project.id,
            user_id=user.id,
            role="player",
        ))
        db.commit()

    try:
        send_verification_email(user.email, user.username, token)
    except Exception:
        logger.exception(
            "Failed to send verification email after registration: user_id=%s email=%s",
            user.id,
            user.email,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "verification_email_delivery_failed",
                "message": VERIFICATION_DELIVERY_ERROR,
                "email": user.email,
            },
        )

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "karma": user.karma,
        "email_verified": user.email_verified,
        "message": "Письмо подтверждения отправлено",
    }


@router.post("/email/verify")
def verify_email(data: EmailVerificationRequest, db: Session = Depends(get_db)):
    token_hash = hash_verification_token(data.token)
    user = db.query(User).filter(
        User.email_verification_token_hash == token_hash
    ).first()
    now = datetime.now(timezone.utc)
    if not user or not user.email_verification_expires_at:
        raise HTTPException(status_code=400, detail="Ссылка подтверждения недействительна или истекла")
    expires_at = user.email_verification_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=400, detail="Ссылка подтверждения недействительна или истекла")

    user.email_verified = True
    user.email_verified_at = now
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    db.commit()
    return {"message": "Адрес электронной почты подтверждён", "email_verified": True}


@router.post("/email/resend")
def resend_verification_email(data: EmailResendRequest, db: Session = Depends(get_db)):
    normalized_email = data.email.lower()
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    generic_response = {
        "message": "Если аккаунт ожидает подтверждения, новое письмо отправлено."
    }
    if not user or user.email_verified:
        return generic_response

    token = issue_verification_token(user)
    db.commit()
    try:
        send_verification_email(user.email, user.username, token)
    except Exception:
        logger.exception(
            "Failed to resend verification email: user_id=%s email=%s",
            user.id,
            user.email,
        )
        raise HTTPException(
            status_code=503,
            detail={
                "code": "verification_email_delivery_failed",
                "message": "Не удалось отправить письмо подтверждения. Попробуйте позже.",
                "email": user.email,
            },
        )
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
            detail="Неверное имя пользователя, адрес электронной почты или пароль"
        )

    if not verify_password(
        form_data.password,
        user.hashed_password
    ):
        record_failed_login(request, form_data.username)
        raise HTTPException(
            status_code=401,
            detail="Неверное имя пользователя, адрес электронной почты или пароль"
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


@router.post("/password/forgot")
def forgot_password(
    data: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    normalized_email = data.email.lower()
    assert_password_reset_allowed(request, normalized_email)
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    response = {"message": PASSWORD_RESET_REQUEST_MESSAGE}
    if not user:
        return response

    token = issue_password_reset_token(user)
    db.commit()
    try:
        send_password_reset_email(user.email, user.username, token)
    except Exception:
        logger.exception(
            "Failed to send password reset email: user_id=%s email=%s",
            user.id,
            user.email,
        )
    return response


@router.post("/password/reset")
def reset_password(data: PasswordResetConfirm, db: Session = Depends(get_db)):
    reject_oversized_password(data.password)
    reject_oversized_password(data.password_confirmation)
    password_policy_error = new_password_policy_error(data.password)
    if password_policy_error:
        raise HTTPException(status_code=422, detail=password_policy_error)
    if data.password != data.password_confirmation:
        raise HTTPException(status_code=422, detail="Пароли не совпадают")

    token_hash = hash_verification_token(data.token)
    user = (
        db.query(User)
        .filter(User.password_reset_token_hash == token_hash)
        .with_for_update()
        .first()
    )
    now = datetime.now(timezone.utc)
    if not user or not user.password_reset_expires_at:
        raise HTTPException(status_code=400, detail=INVALID_PASSWORD_RESET_LINK)
    expires_at = user.password_reset_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        db.commit()
        raise HTTPException(status_code=400, detail=INVALID_PASSWORD_RESET_LINK)

    user.hashed_password = hash_password(data.password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    db.commit()
    return {"message": "Пароль успешно изменён"}

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
            detail="Пользователь не найден"
        )

    return user

@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
    x_project_id: int | None = Header(default=None, alias="X-Project-ID"),
    db: Session = Depends(get_db),
):
    membership = None
    if x_project_id is not None:
        membership = db.query(ProjectMembership).filter(
            ProjectMembership.project_id == x_project_id,
            ProjectMembership.user_id == current_user.id,
        ).first()
        if not current_user.is_owner and not membership:
            raise HTTPException(status_code=403, detail="Project permissions required")
    effective_role = Role.OWNER if current_user.is_owner else membership.role if membership else current_user.role
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "karma": membership.karma if membership else current_user.karma,
        "role": effective_role,
        "is_admin": is_admin_role(effective_role),
        "is_owner": current_user.is_owner,
        "is_head_admin": effective_role == Role.HEAD_ADMIN,
        "email_verified": current_user.email_verified,
        "email_verified_at": current_user.email_verified_at,
    }
