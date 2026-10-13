"""Подвал таблицы: «Показано …» и переключатель страниц."""

from typing import Callable, Tuple

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout

from pharmacy.ui.widgets.common import Line, clear_layout, label
from pharmacy.ui.widgets.controls import Pagination


def fill_footer(
    footer: QVBoxLayout,
    page: int,
    pages: int,
    total: int,
    start: int,
    shown: int,
    on_page: Callable[[int], None],
) -> Tuple[QLabel, Pagination]:
    """Заново собирает подвал таблицы.

    Args:
        footer: Раскладка подвала (старое содержимое удаляется).
        page: Текущая страница.
        pages: Сколько всего страниц.
        total: Сколько всего строк.
        start: Сколько строк стоит на прошлых страницах.
        shown: Сколько строк на этой странице.
        on_page: Вызывается с номером страницы, которую выбрали.

    Returns:
        Подпись «Показано …» и переключатель страниц.
    """
    clear_layout(footer)
    footer.addWidget(Line("line"))
    row = QHBoxLayout()
    row.setContentsMargins(14, 10, 14, 10)
    text = f"Показано {start + 1}–{start + shown} из {total}" if shown else None
    summary = label(text or "Показано 0 из 0", "small", "ink_2")
    pagination = Pagination(page, pages, on_page)
    row.addWidget(summary)
    row.addStretch(1)
    row.addWidget(pagination)
    footer.addLayout(row)
    return summary, pagination
