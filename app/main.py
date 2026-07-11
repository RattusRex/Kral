import os
import json
from datetime import datetime
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
from app.api.karma_shop import router as karma_shop_router
from app.api.recruitments import router as recruitments_router
from app.api.content import router as content_router
from app.models.chat import ChatMessage
from app.models.recruitment import GameApplication, GameRecruitment, RecruitmentMessage
from app.models.content import ContentBlock
from app.models.project import DEFAULT_FEATURES, DEFAULT_PROJECT_NAME, Project, ProjectAuditLog, ProjectMembership
from app.api.projects import router as projects_router
from app.core.calendar import GAME_EPOCH
from app.core.security import hash_password
from app.core.roles import Role
from app.core.env import load_env
from app.core.request_limits import RequestBodyLimitMiddleware
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
        role=Role.OWNER,
        email_verified=True,
        email_verified_at=datetime.now().astimezone(),
    ))
    db.commit()


def seed_default_project(db: Session) -> None:
    owner = db.query(User).filter(User.role == Role.OWNER).order_by(User.id).first()
    if not owner:
        return
    project = db.query(Project).filter(Project.name == DEFAULT_PROJECT_NAME).first()
    if not project:
        project = Project(
            name=DEFAULT_PROJECT_NAME,
            slug="epoch-of-catastrophe",
            is_default=True,
            owner_id=owner.id,
            settings={},
            features=dict(DEFAULT_FEATURES),
        )
        db.add(project)
        db.flush()
    for user in db.query(User).all():
        if not db.query(ProjectMembership).filter_by(project_id=project.id, user_id=user.id).first():
            db.add(ProjectMembership(
                project_id=project.id, user_id=user.id,
                role="admin" if user.is_admin else "player",
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


def migrate_email_verification() -> None:
    """Keep existing accounts active; only registrations after this migration wait for email."""
    boolean_default = "1" if engine.dialect.name == "sqlite" else "TRUE"
    timestamp_type = "TIMESTAMP" if engine.dialect.name == "sqlite" else "TIMESTAMP WITH TIME ZONE"
    ensure_column(
        "users",
        "email_verified",
        f"BOOLEAN NOT NULL DEFAULT {boolean_default}",
    )
    ensure_column("users", "email_verified_at", timestamp_type)
    ensure_column("users", "email_verification_token_hash", "VARCHAR(64)")
    ensure_column("users", "email_verification_expires_at", timestamp_type)
    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE users SET email_verified = TRUE WHERE email_verified IS NULL"
        ))


def ensure_schema_columns() -> None:
    # Project migration depends on a global owner. Legacy databases do not
    # have the role or email-verification columns yet, so migrate the user
    # table and promote the seeded administrator before querying project
    # ownership or creating the default project.
    migrate_user_roles()
    migrate_email_verification()
    with SessionLocal() as db:
        seed_admin(db)

    # Projects created before feature flags were introduced only have the
    # upstream ecosystem columns. Add the optional metadata in place.
    ensure_column("projects", "slug", "VARCHAR(100)")
    ensure_column("projects", "is_default", "BOOLEAN NOT NULL DEFAULT FALSE")
    ensure_column("projects", "features", "JSON NOT NULL DEFAULT '{}'")
    # Existing installations predate projects; all legacy characters belong to
    # the campaign's original ecosystem.
    with SessionLocal() as db:
        seed_default_project(db)
        default_project_id = db.query(Project.id).filter(
            Project.name == DEFAULT_PROJECT_NAME
        ).scalar()
    ensure_column(
        "characters", "project_id",
        f"INTEGER REFERENCES projects(id) DEFAULT {default_project_id}"
    )
    for table_name in ("chat_messages", "content_blocks", "game_recruitments"):
        ensure_column(
            table_name, "project_id",
            f"INTEGER REFERENCES projects(id) DEFAULT {default_project_id}"
        )
    ensure_column("characters", "temp_hp", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("characters", "speed", "INTEGER NOT NULL DEFAULT 30")
    ensure_column("characters", "skill_proficiencies", "JSON NOT NULL DEFAULT '[]'")
    ensure_column("characters", "class_levels", "JSON NOT NULL DEFAULT '[]'")
    ensure_column("characters", "skill_expertise", "JSON NOT NULL DEFAULT '[]'")
    ensure_column(
        "characters",
        "saving_throw_proficiencies",
        "JSON NOT NULL DEFAULT '[]'"
    )
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
    ensure_column("downtime_entries", "tools", "VARCHAR(255)")
    ensure_column("downtime_entries", "proficiency_modifier", "INTEGER")
    ensure_column("downtime_entries", "income_copper", "INTEGER")
    ensure_column("shop_transaction_logs", "total_copper", "INTEGER")
    for table_name in ("shop_transaction_logs", "market_sale_logs", "karma_purchases"):
        ensure_column(table_name, "actor_id", "INTEGER")
        ensure_column(table_name, "actor_username", "VARCHAR(50)")
    ensure_column(
        "shop_quotes",
        "searcher_type",
        "VARCHAR(32) NOT NULL DEFAULT 'character'"
    )
    ensure_column("inventories", "notes", "TEXT NOT NULL DEFAULT ''")
    ensure_column(
        "game_recruitments",
        "status",
        "VARCHAR(20) NOT NULL DEFAULT 'upcoming'",
    )
    ensure_column("recruitment_messages", "user_id", "INTEGER REFERENCES users(id)")
    ensure_column("recruitment_messages", "username", "VARCHAR(50)")
    ensure_column(
        "recruitment_messages", "is_system",
        "BOOLEAN NOT NULL DEFAULT FALSE",
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE projects SET is_default = TRUE "
                "WHERE name = :name AND NOT EXISTS "
                "(SELECT 1 FROM projects WHERE is_default = TRUE)"
            ),
            {"name": DEFAULT_PROJECT_NAME},
        )
        connection.execute(
            text("UPDATE characters SET project_id = :project_id WHERE project_id IS NULL"),
            {"project_id": default_project_id},
        )
        for table_name in ("chat_messages", "content_blocks", "game_recruitments"):
            connection.execute(text(
                f"UPDATE {table_name} SET project_id = :project_id WHERE project_id IS NULL"
            ), {"project_id": default_project_id})
        rows = connection.execute(text(
            "SELECT id, class_name, level, class_levels FROM characters"
        )).mappings()
        for row in rows:
            if row["class_levels"] not in (None, [], "[]"):
                continue
            connection.execute(
                text("UPDATE characters SET class_levels = :levels WHERE id = :id"),
                {
                    "id": row["id"],
                    "levels": json.dumps([{
                        "class_name": row["class_name"],
                        "level": row["level"],
                    }]),
                },
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_columns()
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_default_project(db)
    finally:
        db.close()
    yield

_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app = FastAPI(lifespan=lifespan)

app.add_middleware(RequestBodyLimitMiddleware)

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
app.include_router(karma_shop_router, prefix="/api")
app.include_router(recruitments_router, prefix="/api")
app.include_router(content_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(projects_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Мики маус"}


if __name__ == "__main__":
    _reload = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    uvicorn.run("app.main:app", reload=_reload)
