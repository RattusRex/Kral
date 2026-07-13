from datetime import date, datetime, timedelta

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Date, DateTime, Integer, JSON, String, Boolean
from app.core.calendar import GAME_EPOCH
from app.db.database import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str]

    class_name: Mapped[str]

    class_levels: Mapped[list[dict]] = mapped_column(
        JSON,
        default=list
    )

    subclass: Mapped[str] = mapped_column(
        default=""
    )

    race: Mapped[str] = mapped_column(
        default=""
    )

    background: Mapped[str] = mapped_column(
        default=""
    )

    strength: Mapped[int] = mapped_column(
        default=10
    )

    dexterity: Mapped[int] = mapped_column(
        default=10
    )

    constitution: Mapped[int] = mapped_column(
        default=10
    )

    intelligence: Mapped[int] = mapped_column(
        default=10
    )

    wisdom: Mapped[int] = mapped_column(
        default=10
    )

    charisma: Mapped[int] = mapped_column(
        default=10
    )

    investigation: Mapped[int] = mapped_column(
        default=0
    )

    skill_proficiencies: Mapped[list[str]] = mapped_column(
        JSON,
        default=list
    )

    skill_expertise: Mapped[list[str]] = mapped_column(
        JSON,
        default=list
    )

    saving_throw_proficiencies: Mapped[list[str]] = mapped_column(
        JSON,
        default=list
    )

    personal_hireling_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    personal_hireling_acquired_at: Mapped[date] = mapped_column(
        Date,
        default=GAME_EPOCH
    )

    personal_hireling_investigation: Mapped[int] = mapped_column(
        default=0
    )

    simulacrum_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    simulacrum_created_at: Mapped[date] = mapped_column(
        Date,
        default=GAME_EPOCH
    )

    simulacrum_investigation: Mapped[int] = mapped_column(
        default=0
    )

    hp: Mapped[int] = mapped_column(
        default=0
    )

    temp_hp: Mapped[int] = mapped_column(
        default=0
    )

    armor_class: Mapped[int] = mapped_column(
        default=10
    )

    speed: Mapped[int] = mapped_column(
        default=30
    )

    level: Mapped[int] = mapped_column(
        default=1
    )

    xp: Mapped[int] = mapped_column(
        default=0
    )

    is_dead: Mapped[bool] = mapped_column(
        Boolean,
        default=False
    )

    route: Mapped[str]

    # In-world creation date — the starting point for the free-day calendar.
    # Defaults to the game epoch so existing characters keep a sensible value.
    game_created_at: Mapped[date] = mapped_column(
        Date,
        default=GAME_EPOCH
    )


    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id")
    )
    owner = relationship(
        "User",
        back_populates="characters"
    )
    project = relationship(
        "Project",
        back_populates="characters",
    )

    inventory = relationship(
        "Inventory",
        back_populates="character",
        uselist=False,
        cascade="all, delete-orphan"
    )

    attacks = relationship(
        "CharacterAttack",
        back_populates="character",
        cascade="all, delete-orphan"
    )

    downtime_entries = relationship(
        "DowntimeEntry",
        back_populates="character",
        cascade="all, delete-orphan",
        order_by="DowntimeEntry.start_date"
    )

    game_applications = relationship(
        "GameApplication",
        back_populates="character",
        cascade="all, delete-orphan",
    )


class DowntimeEntry(Base):
    """A span of in-world days a character spent on out-of-game activities."""

    __tablename__ = "downtime_entries"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id")
    )

    # First busy day of the span.
    start_date: Mapped[date] = mapped_column(
        Date
    )

    # Number of consecutive busy days, starting at ``start_date``.
    days: Mapped[int] = mapped_column(
        Integer,
        default=1
    )

    # Human-readable reason ("крафт", "поиск покупателя", ...).
    reason: Mapped[str] = mapped_column(
        String(255),
        default=""
    )

    # Origin of the entry: "manual" for journal entries, "shop" for
    # automatic deductions made by the shop mechanics.
    source: Mapped[str] = mapped_column(
        String(32),
        default="manual"
    )

    # Which actor spent the day: character, personal_hireling, or simulacrum.
    agent_type: Mapped[str] = mapped_column(
        String(32),
        default="character"
    )

    tools: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proficiency_modifier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    income_copper: Mapped[int | None] = mapped_column(Integer, nullable=True)

    @property
    def end_date(self) -> date:
        """Return the inclusive final busy day of this entry."""
        return self.start_date + timedelta(days=max(1, self.days) - 1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    character = relationship(
        "Character",
        back_populates="downtime_entries"
    )


class CalendarAuditLog(Base):
    """Audit trail of administrative changes to a character's calendar.

    Every time an administrator (or owner / head admin) creates, edits or
    deletes a downtime entry the change is recorded here so the history of
    calendar corrections can be reviewed.  The log captures *who* performed the
    action, on *which* character, the *type* of action and *when* it happened.
    """

    __tablename__ = "calendar_audit_logs"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

    # Who performed the action.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)

    username: Mapped[str] = mapped_column(
        String(50)
    )

    # Acting user's role at the time of the action ("owner", "admin", ...).
    role: Mapped[str] = mapped_column(
        String(20),
        default=""
    )

    # Which character's calendar was affected.
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id")
    )

    character_name: Mapped[str] = mapped_column(
        String(255)
    )

    # Type of action: "create", "update" or "delete".
    action: Mapped[str] = mapped_column(
        String(20)
    )

    # The affected downtime entry id (may be null after a delete).
    entry_id: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    # Human-readable summary of what changed.
    details: Mapped[str] = mapped_column(
        String(512),
        default=""
    )


class CharacterAttack(Base):
    __tablename__ = "character_attacks"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(255)
    )

    attack_bonus: Mapped[int] = mapped_column(
        default=0
    )

    damage: Mapped[str] = mapped_column(
        String(255),
        default=""
    )

    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id")
    )
    character = relationship(
        "Character",
        back_populates="attacks"
    )
