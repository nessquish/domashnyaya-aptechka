"""Работа с датами.

Пользователь вводит и видит даты в виде ДД.ММ.ГГГГ, а в базе они хранятся
в виде ГГГГ-ММ-ДД (так их можно сравнивать и сортировать прямо в SQL).
"""

from datetime import date, datetime
from typing import Optional

USER_DATE_FORMAT = "%d.%m.%Y"


def parse_user_date(text: str) -> date:
    """Превращает текст ДД.ММ.ГГГГ в дату.

    Args:
        text: Дата, введённая пользователем.

    Returns:
        Дата.

    Raises:
        ValueError: Если текст не похож на дату или такой даты не бывает.
    """
    return datetime.strptime(text.strip(), USER_DATE_FORMAT).date()


def format_user_date(value: Optional[date]) -> str:
    """Записывает дату в виде ДД.ММ.ГГГГ (для пустой даты возвращает пустую строку)."""
    return value.strftime(USER_DATE_FORMAT) if value else ""


def stored_date(created_at: str) -> date:
    """Дата из строки базы «ГГГГ-ММ-ДД ЧЧ:ММ:СС» (время отбрасывается)."""
    return date.fromisoformat(created_at[:10])


def format_created(created_at: str) -> str:
    """Дату добавления из базы показывает как ДД.ММ.ГГГГ."""
    return format_user_date(stored_date(created_at))


def days_until(target: date, today: Optional[date] = None) -> int:
    """Считает, сколько дней осталось до даты.

    Args:
        target: Дата, до которой считаем.
        today: Сегодняшняя дата (по умолчанию берётся из системы).

    Returns:
        Число дней: положительное, если дата впереди, и отрицательное,
        если уже прошла.
    """
    return (target - (today or date.today())).days
