import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from app.api.users import router as users_router
from app.db.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.character import (
    CalendarAuditLog,
    Character,
    CharacterAttack,
    DowntimeEntry,
)
from app.api.characters import router as character_router
from app.models.inventory import Inventory, InventoryItem
from app.api.inventory import router as inventory_router
from app.api.calendar import router as calendar_router
from app.api.admin import router as admin_router
from app.api.attacks import router as attacks_router
from app.api.chat import router as chat_router
from app.models.chat import ChatMessage
from app.core.calendar import GAME_EPOCH
from app.core.security import hash_password
from app.core.roles import Role
from app.core.env import load_env
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

load_env()

_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
if not _ADMIN_PASSWORD:
    raise RuntimeError(
        "ADMIN_PASSWORD environment variable is not set. "
        "Set a strong password for the default admin account in your .env file."
    )


def seed_admin(db: Session) -> None:
    admin = db.query(User).filter(User.username == "admin").first()
    if admin:
        if admin.role != Role.OWNER:
            admin.role = Role.OWNER
            db.commit()
        return

    db.add(User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password(_ADMIN_PASSWORD),
        role=Role.OWNER
    ))
    db.commit()


def ensure_column(table_name: str, column_name: str, column_definition: str) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name in columns:
        return

    with engine.begin() as connection:
        connection.execute(text(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        ))


def migrate_user_roles() -> None:
    """Add the ``role`` column and backfill it from the legacy ``is_admin``.

    Older databases stored privileges in a boolean ``is_admin`` column. The
    role system replaces it with a string ``role`` column, so any existing
    administrators are migrated to the ``admin`` role and everyone else to
    ``player``.
    """
    ensure_column("users", "role", f"VARCHAR(20) NOT NULL DEFAULT '{Role.PLAYER}'")

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_admin" not in columns:
        return

    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE users SET role = :admin "
            "WHERE is_admin = TRUE AND (role IS NULL OR role = '' OR role = :player)"
        ), {"admin": Role.ADMIN, "player": Role.PLAYER})
        connection.execute(text(
            "UPDATE users SET role = :player WHERE role IS NULL OR role = ''"
        ), {"player": Role.PLAYER})


def ensure_schema_columns() -> None:
    ensure_column("characters", "temp_hp", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("characters", "speed", "INTEGER NOT NULL DEFAULT 30")
    ensure_column(
        "characters",
        "game_created_at",
        f"DATE NOT NULL DEFAULT '{GAME_EPOCH.isoformat()}'"
    )
    ensure_column(
        "characters",
        "personal_hireling_enabled",
        "BOOLEAN NOT NULL DEFAULT FALSE"
    )
    ensure_column(
        "characters",
        "personal_hireling_acquired_at",
        f"DATE NOT NULL DEFAULT '{GAME_EPOCH.isoformat()}'"
    )
    ensure_column(
        "characters",
        "personal_hireling_investigation",
        "INTEGER NOT NULL DEFAULT 0"
    )
    ensure_column(
        "characters",
        "simulacrum_enabled",
        "BOOLEAN NOT NULL DEFAULT FALSE"
    )
    ensure_column(
        "characters",
        "simulacrum_created_at",
        f"DATE NOT NULL DEFAULT '{GAME_EPOCH.isoformat()}'"
    )
    ensure_column(
        "characters",
        "simulacrum_investigation",
        "INTEGER NOT NULL DEFAULT 0"
    )
    ensure_column(
        "downtime_entries",
        "agent_type",
        "VARCHAR(32) NOT NULL DEFAULT 'character'"
    )
    ensure_column(
        "shop_quotes",
        "searcher_type",
        "VARCHAR(32) NOT NULL DEFAULT 'character'"
    )
    ensure_column("inventories", "notes", "TEXT NOT NULL DEFAULT ''")
    migrate_user_roles()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_columns()
    db = SessionLocal()
    try:
        seed_admin(db)
    finally:
        db.close()
    yield

_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inventory_router, prefix="/api")
app.include_router(calendar_router, prefix="/api")
app.include_router(character_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(attacks_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(users_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Мики маус"}


if __name__ == "__main__":
    _reload = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    uvicorn.run("app.main:app", reload=_reload)
