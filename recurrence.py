import calendar
from datetime import timedelta


def _add_month(due_at):
    """Same day next month, clamped to the month's last day (Jan 31 -> Feb 28)."""
    year, month = (due_at.year + 1, 1) if due_at.month == 12 else (due_at.year, due_at.month + 1)
    day = min(due_at.day, calendar.monthrange(year, month)[1])
    return due_at.replace(year=year, month=month, day=day)


def next_due_at(due_at, recurrence):
    if recurrence == "daily":
        return due_at + timedelta(days=1)
    if recurrence == "weekly":
        return due_at + timedelta(weeks=1)
    return _add_month(due_at)
