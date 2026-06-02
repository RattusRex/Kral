from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
from app.api.users import router as users_router
from app.db.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.character import Character, CharacterAttack
from app.api.characters import router as character_router
from app.models.inventory import Inventory, InventoryItem
from app.api.inventory import router as inventory_router
from app.api.admin import router as admin_router
from app.api.attacks import router as attacks_router
from app.api.chat import router as chat_router
from app.models.chat import ChatMessage
from app.core.security import hash_password
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


def seed_admin(db: Session) -> None:
    admin = db.query(User).filter(User.username == "admin").first()
    if admin:
        if not admin.is_admin:
            admin.is_admin = True
            db.commit()
        return

    db.add(User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password("admin123"),
        is_admin=True
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


def ensure_schema_columns() -> None:
    ensure_column("characters", "temp_hp", "INTEGER NOT NULL DEFAULT 0")
    ensure_column("characters", "speed", "INTEGER NOT NULL DEFAULT 30")
    ensure_column("inventories", "notes", "TEXT NOT NULL DEFAULT ''")


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

app = FastAPI(lifespan=lifespan)
app.include_router(inventory_router, prefix="/api")
app.include_router(character_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(attacks_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(users_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Мики маус"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", reload=True)
