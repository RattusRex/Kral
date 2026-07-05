from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
import os

from app.core.env import load_env


# Populate environment variables from a project-level `.env` file before
# reading DATABASE_URL. Existing variables (set by the shell, by
# scripts/dev.mjs, or by the test suite) always take precedence.
load_env()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Set it in the environment or project .env file "
        "before starting the backend."
    )

engine_kwargs: dict = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    # In-memory SQLite databases live for the lifetime of a single
    # connection. The TestClient serves requests from a worker thread, so
    # without a shared connection the test setup and the request handlers
    # would see different (empty) databases. StaticPool keeps one shared
    # connection so schema and data created in tests stay visible.
    if ":memory:" in DATABASE_URL or DATABASE_URL in ("sqlite://", "sqlite:///:memory:"):
        engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)


class Base(DeclarativeBase):
    pass
