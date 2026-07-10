"""Game calendar helpers.

The game world tracks in-world time starting from :data:`GAME_EPOCH`.  Each
character has its own in-world creation date which is the starting point for
counting how many "free" (downtime) days the character has accumulated.

Free days are the elapsed in-world days that have not yet been spent on
downtime activities (crafting, searching for buyers/sellers, research, etc.).
When a time-consuming activity is performed the system always spends the
*oldest* available free days first, so a character's busy timeline stays
contiguous and chronologically consistent with the game world.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Sequence


# The game server started counting in-world time on this date.  Characters can
# never have a creation date (or downtime) earlier than this.
GAME_EPOCH = date(2025, 6, 1)


def work_income_copper(proficiency_modifier: int, days: int) -> int:
    """Return campaign work income in copper for a modifier and day count."""
    if days <= 0:
        raise ValueError("Work days must be positive")
    daily_income = {
        3: 50, 4: 100, 5: 200, 6: 500,
        7: 1500, 8: 2500, 9: 4000,
    }.get(proficiency_modifier)
    if daily_income is None:
        daily_income = (
            2 if proficiency_modifier <= 2
            else 4000 + (proficiency_modifier - 9) * 1000
        )
    return daily_income * days


def current_game_date() -> date:
    """Return the current in-world date.

    The game world advances in lockstep with real time, so the current
    in-world date is simply today's real date.  Kept as a dedicated helper so
    the behaviour is easy to override in tests.
    """
    return date.today()


def occupied_days(
    entries: Iterable["DowntimeLike"],
    window_start: date | None = None,
    window_end: date | None = None,
) -> set[date]:
    """Return busy days, optionally bounded to ``[window_start, window_end)``."""
    days: set[date] = set()
    if (
        window_start is not None
        and window_end is not None
        and window_start >= window_end
    ):
        return days

    for entry in entries:
        entry_days = max(0, entry.days)
        if entry_days == 0:
            continue

        start_offset = 0
        if window_start is not None and entry.start_date < window_start:
            start_offset = min(
                entry_days,
                (window_start - entry.start_date).days,
            )

        end_offset = entry_days
        if window_end is not None:
            end_offset = min(
                entry_days,
                (window_end - entry.start_date).days,
            )

        if end_offset <= start_offset:
            continue

        for offset in range(start_offset, end_offset):
            days.add(entry.start_date + timedelta(days=offset))
    return days


def count_busy_days(
    entries: Iterable["DowntimeLike"],
    created_at: date,
    current_date: date,
) -> int:
    """Count busy days that fall inside the character's active window.

    Days outside ``[created_at, current_date)`` are ignored so that a stray
    entry can never make the busy total exceed the elapsed total.
    """
    return len(occupied_days(entries, created_at, current_date))


def total_elapsed_days(created_at: date, current_date: date) -> int:
    """Return the number of in-world days that have passed since creation."""
    return max(0, (current_date - created_at).days)


def free_day_dates(
    entries: Iterable["DowntimeLike"],
    created_at: date,
    current_date: date,
) -> list[date]:
    """Return the ordered list of still-free days, oldest first."""
    busy = occupied_days(entries, created_at, current_date)
    free: list[date] = []
    day = created_at
    while day < current_date:
        if day not in busy:
            free.append(day)
        day += timedelta(days=1)
    return free


def group_consecutive_days(days: Sequence[date]) -> list[tuple[date, int]]:
    """Group sorted ``days`` into contiguous ``(start_date, length)`` runs."""
    runs: list[tuple[date, int]] = []
    for day in days:
        if runs:
            start, length = runs[-1]
            if start + timedelta(days=length) == day:
                runs[-1] = (start, length + 1)
                continue
        runs.append((day, 1))
    return runs


def plan_oldest_day_spend(
    entries: Iterable["DowntimeLike"],
    created_at: date,
    current_date: date,
    days: int,
) -> list[tuple[date, int]]:
    """Plan how to spend ``days`` using the oldest available free days.

    Returns a list of ``(start_date, length)`` runs to record.  Raises
    :class:`ValueError` if there are not enough free days available.
    """
    if days <= 0:
        raise ValueError("days must be positive")

    free = free_day_dates(entries, created_at, current_date)
    if len(free) < days:
        raise ValueError("not enough free days")

    return group_consecutive_days(free[:days])


def calendar_summary(
    entries: Iterable["DowntimeLike"],
    created_at: date,
    current_date: date | None = None,
) -> dict:
    """Build the calendar summary payload for a character."""
    current = current_date or current_game_date()
    total = total_elapsed_days(created_at, current)
    busy = count_busy_days(entries, created_at, current)
    free = max(0, total - busy)
    return {
        "game_epoch": GAME_EPOCH,
        "created_at": created_at,
        "current_date": current,
        "total_days": total,
        "busy_days": busy,
        "free_days": free,
    }


class DowntimeLike:  # pragma: no cover - typing helper only
    """Structural type used purely for static reference in annotations."""

    start_date: date
    days: int
