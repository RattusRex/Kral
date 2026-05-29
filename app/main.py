from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
from app.api.users import router as users_router
from app.db.database import Base, engine
from app.models.user import User
from app.models.character import Character
from app.api.characters import router as character_router
from app.models.inventory import Inventory, InventoryItem
from app.api.inventory import router as inventory_router
from app.api.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(inventory_router)
app.include_router(character_router)
app.include_router(admin_router)
app.include_router(users_router)

@app.get("/")
def root():
    return {"message": "Мики маус"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", reload=True)