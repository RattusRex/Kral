from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:GalU5TA1@localhost:5432/EpohaTruda"
)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


class Base(DeclarativeBase):
    pass
