"""Unit tests for the game calendar core logic (app/core/calendar.py)."""

from datetime import date

import pytest

from app.core import calendar as game_calendar


class FakeEntry:
    """Lightweight stand-in for a DowntimeEntry row."""

    def __init__(self, start_date: date, days: int):
        self.start_date = start_date
        self.days = days


def test_game_epoch_is_first_of_june_2025():
    assert game_calendar.GAME_EPOCH == date(2025, 6, 1)


def test_total_elapsed_matches_issue_first_example():
    # Created 01.06.2025, current 01.09.2025 -> 92 days passed.
    total = game_calendar.total_elapsed_days(date(2025, 6, 1), date(2025, 9, 1))
    assert total == 92


def test_total_elapsed_matches_issue_second_example():
    # Created 15.09.2025, current 10.03.2026 -> 176 days passed.
    total = game_calendar.total_elapsed_days(date(2025, 9, 15), date(2026, 3, 10))
    assert total == 176


def test_free_days_is_total_minus_busy():
    # 92 elapsed days, 35 busy days -> 57 free (issue example).
    entries = [FakeEntry(date(2025, 6, 1), 35)]
    summary = game_calendar.calendar_summary(
        entries, date(2025, 6, 1), date(2025, 9, 1)
    )
    assert summary["total_days"] == 92
    assert summary["busy_days"] == 35
    assert summary["free_days"] == 57


def test_busy_days_outside_window_are_ignored():
    # An entry that runs past the current date should only count the days
    # that fall inside [created, current).
    entries = [FakeEntry(date(2025, 8, 30), 10)]
    summary = game_calendar.calendar_summary(
        entries, date(2025, 6, 1), date(2025, 9, 1)
    )
    # Only 30.08 and 31.08 are inside the window (current 01.09 is exclusive).
    assert summary["busy_days"] == 2


def test_occupied_days_can_be_bounded_to_active_window():
    entries = [FakeEntry(date(2025, 6, 1), 10_000)]
    days = game_calendar.occupied_days(
        entries,
        date(2025, 6, 1),
        date(2025, 6, 10),
    )
    assert days == {date(2025, 6, day) for day in range(1, 10)}


def test_overlapping_entries_count_each_day_once():
    entries = [
        FakeEntry(date(2025, 6, 1), 5),
        FakeEntry(date(2025, 6, 3), 5),  # overlaps 03-05.06
    ]
    summary = game_calendar.calendar_summary(
        entries, date(2025, 6, 1), date(2025, 7, 1)
    )
    # Days 01-07.06 = 7 distinct busy days.
    assert summary["busy_days"] == 7


def test_oldest_days_are_spent_first():
    # Free days 01.08-05.08, action takes 3 days -> 04.08, 05.08 remain free.
    created = date(2025, 8, 1)
    current = date(2025, 8, 6)  # exclusive -> free days are 01-05.08
    runs = game_calendar.plan_oldest_day_spend([], created, current, 3)
    assert runs == [(date(2025, 8, 1), 3)]

    spent = [FakeEntry(start, length) for start, length in runs]
    remaining = game_calendar.free_day_dates(spent, created, current)
    assert remaining == [date(2025, 8, 4), date(2025, 8, 5)]


def test_oldest_days_skip_already_busy_days_and_stay_contiguous():
    created = date(2025, 6, 1)
    current = date(2025, 6, 11)
    # 03.06 and 04.06 are already busy.
    existing = [FakeEntry(date(2025, 6, 3), 2)]
    runs = game_calendar.plan_oldest_day_spend(existing, created, current, 4)
    # Oldest free days: 01,02 (then skip 03,04) then 05,06.
    assert runs == [(date(2025, 6, 1), 2), (date(2025, 6, 5), 2)]


def test_plan_raises_when_not_enough_free_days():
    created = date(2025, 6, 1)
    current = date(2025, 6, 4)  # only 3 free days: 01,02,03
    with pytest.raises(ValueError):
        game_calendar.plan_oldest_day_spend([], created, current, 5)


def test_plan_rejects_non_positive_days():
    with pytest.raises(ValueError):
        game_calendar.plan_oldest_day_spend([], date(2025, 6, 1), date(2025, 7, 1), 0)
