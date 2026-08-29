"""JLPT exam countdown helpers."""

from datetime import date
from typing import Optional

JLPT_N2_DATE = date(2026, 12, 6)


def format_jlpt_countdown(today: Optional[date] = None) -> str:
    """Return the signed day and week countdown to the JLPT N2 exam."""
    current_date = today or date.today()
    days_remaining = (JLPT_N2_DATE - current_date).days
    sign = -1 if days_remaining < 0 else 1
    weeks, remaining_days = divmod(abs(days_remaining), 7)

    week_label = "week" if weeks == 1 else "weeks"
    parts = [f"{sign * weeks} {week_label}"]
    if remaining_days:
        day_label = "day" if remaining_days == 1 else "days"
        parts.append(f"{sign * remaining_days} {day_label}")

    day_label = "day" if abs(days_remaining) == 1 else "days"
    return (
        f"JLPT N2 exam countdown: {days_remaining} {day_label} "
        f"({', '.join(parts)})"
    )
