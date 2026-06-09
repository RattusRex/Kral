from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

from app.core.env import load_env


# Populate environment variables from a project-level `.env` file before
# reading DATABASE_URL. Existing variables (set by the shell, by
# scripts/dev.mjs, or by the test suite) always take precedence.
load_env()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:GalU5TA1@localhost:5432/EpohaTruda")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. PostgreSQL is required.")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


class Base(DeclarativeBase):
    pass
