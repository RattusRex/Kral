from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
from app.api.users import router as users_router
from app.db.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.character import Character
from app.api.characters import router as character_router
from app.models.inventory import Inventory, InventoryItem
from app.api.inventory import router as inventory_router
from app.api.admin import router as admin_router
from app.core.security import hash_password
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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
app.include_router(users_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Мики маус"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", reload=True)
