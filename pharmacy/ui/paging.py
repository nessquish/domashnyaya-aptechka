"""Сколько строк таблицы помещается на экране.

Таблица «Моей аптечки» и списка покупок занимает всё окно до низа: число строк
на странице зависит от высоты окна, масштаба и размера текста. Страниц от этого
становится меньше, а пустого места под таблицей нет.
"""

from typing import Dict

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget

DEFAULT_ROWS = 8  # пока окно не измерено
MIN_ROWS = 4
MAX_ROWS = 100
BOTTOM_GAP = 16  # воздух между таблицей и нижним краем окна

AUTO_FIT = True  # тесты выключают подгонку, чтобы страницы были фиксированными

_remembered: Dict[str, int] = {}


def remembered_rows(key: str) -> int:
    """Размер страницы, найденный в прошлый раз (чтобы экран не мигал при открытии)."""
    return _remembered.get(key, DEFAULT_ROWS) if AUTO_FIT else DEFAULT_ROWS


def fitted_rows(
    key: str,
    screen: QWidget,
    card: QWidget,
    table: QWidget,
    header_height: int,
    shown: int,
    current: int,
    viewport_height: int,
    reserve: int = 0,
) -> int:
    """Считает, сколько строк поместится на странице.

    Args:
        key: Имя экрана, под которым запоминается результат.
        screen: Экран раздела.
        card: Карточка с таблицей и подвалом.
        table: Таблица.
        header_height: Высота шапки таблицы.
        shown: Сколько строк показано сейчас.
        current: Размер страницы сейчас.
        viewport_height: Высота видимой области окна.
        reserve: Сколько места оставить про запас (панель действий, пока скрыта).

    Returns:
        Новый размер страницы (не меньше ``MIN_ROWS``).
    """
    if not AUTO_FIT or shown < 1 or viewport_height <= 0 or not screen.isVisible():
        return current
    row_height = (table.height() - header_height) / shown
    if row_height <= 0:
        return current
    bottom = card.mapTo(screen, QPoint(0, card.height())).y()
    free = viewport_height - bottom - BOTTOM_GAP - reserve
    rows = shown + int(free // row_height)
    rows = max(MIN_ROWS, min(rows, MAX_ROWS))
    _remembered[key] = rows
    return rows
