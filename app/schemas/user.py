from pydantic import BaseModel, EmailStr, Field

from app.core.passwords import MAX_PASSWORD_BYTES


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_BYTES)

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_BYTES)

class KarmaUpdate(BaseModel):
    amount: int


class RoleUpdate(BaseModel):
    role: str
