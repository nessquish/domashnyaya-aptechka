"""Окно поиска по программе: товары и настройки, результаты по мере набора."""

from typing import TYPE_CHECKING, List, Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from pharmacy.models import Product
from pharmacy.services.history_service import ACTION_LABELS
from pharmacy.services.notification_service import KIND_LABELS
from pharmacy.ui.screens.shopping import SOURCE_LABELS
from pharmacy.ui.paint import begin, fill_rounded
from pharmacy.ui.search_index import (
    CARD,
    HISTORY,
    MAX_RESULTS,
    NOTIFICATION,
    PRODUCT,
    SHOPPING,
    SearchEntry,
    Target,
    search_sections,
)
from pharmacy.ui.theme import mix, palette
from pharmacy.ui.widgets.common import clickable, clear_layout, label, pad
from pharmacy.ui.widgets.dialog import Modal
from pharmacy.ui import theme
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.field import TextField
from pharmacy.ui.widgets.scroll import ScrollArea
from pharmacy.utils.formatting import format_quantity

if TYPE_CHECKING:
    from pharmacy.ui.app import App

WIDTH = 560
EMPTY_TEXT = "Ничего не найдено"
HINT_TEXT = "Введите название товара, раздела или настройки"
SECTIONS_TITLE = "Разделы и настройки"
ROW_RADIUS = 8
MODAL_MARGIN = 220  # сколько места окна занимают поле, отступы и поля вокруг
MIN_LIST_HEIGHT = 120
MAX_LIST_HEIGHT = 440


class _ResultRow(QWidget):
    """Строка результата: название и подпись, подсвечивается при наведении."""

    def __init__(self, title: str, caption: str, target: Target, command) -> None:
        super().__init__()
        self.target = target
        self.title = title
        self.caption = caption
        self.active = False
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 7, 12, 7)
        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(1)
        texts.addWidget(label(title, "strong", tight=True, bare=True))
        texts.addWidget(label(caption, "caption", "ink_3", tight=True, bare=True))
        row.addLayout(texts, 1)
        clickable(self, lambda: command(target))

    def set_active(self, active: bool) -> None:
        self.active = active
        self.update()

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        if self.active or self.underMouse():
            pal = palette()
            painter = QPainter(self)
            begin(painter)
            fill_rounded(
                painter,
                self.rect().toRectF(),
                ROW_RADIUS,
                mix(pal.card, pal.primary_soft, 0.55),
            )


class SearchModal(Modal):
    """Одно поле ввода и результаты под ним: товары и разделы с настройками."""

    def __init__(self, app: "App", services, user_id: int) -> None:
        """Открывает окно поиска.

        Args:
            app: Окно приложения (оно же переходит к найденному).
            services: Сервисы приложения.
            user_id: Пользователь, чьи товары ищутся.
        """
        super().__init__(app, WIDTH, on_enter=self.open_active)
        self._app = app
        self._services = services
        self._user_id = user_id
        self.rows: List[_ResultRow] = []
        self.group_titles: List[str] = []
        self.active_index = -1
        self.field = TextField(
            placeholder="Поиск по товарам, истории и настройкам…",
            leading_icon="search",
            on_change=self._update,
        )
        self.field.bind_submit(self.open_active)
        self.field.entry.installEventFilter(self)
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(8)
        search_row.addWidget(self.field, 1)
        self.close_button = Button(
            "",
            command=self.close_modal,
            icon="x",
            size="md",
            width=theme.CONTROL_HEIGHT,
        )
        search_row.addWidget(self.close_button)
        self.body.addLayout(search_row)
        # Результаты прокручиваются, если не помещаются в окно.
        self._scroll = ScrollArea(gutter=8)
        self._results = self._scroll.body
        self._results.setContentsMargins(0, 4, 0, 0)
        self._results.setSpacing(0)
        self.body.addWidget(self._scroll)
        self._update()
        self.field.focus_field()

    # --- результаты ---

    def _update(self) -> None:
        """Заново ищет и перестраивает список (вызывается с каждой буквой)."""
        query = self.field.get().strip()
        clear_layout(self._results)
        self.rows = []
        self.group_titles = []
        self.active_index = -1
        if not query:
            self._message(HINT_TEXT)
            QTimer.singleShot(0, self._fit_height)
            return
        found = self._collect(query)
        if not found:
            self._message(EMPTY_TEXT)
            QTimer.singleShot(0, self._fit_height)
            return
        for title, rows in found:
            self._group(title)
            for row_title, caption, target in rows:
                self._add(row_title, caption, target)
        self._set_active(0)
        QTimer.singleShot(0, self._fit_height)

    def _collect(self, query: str):
        """Все места, где есть найденное: группы строк (название, подпись, цель).

        Товар можно открыть в таблице «Моя аптечка» и в карточке; если он есть
        в списке покупок, уведомлениях или истории, то и там.
        """
        services, user_id = self._services, self._user_id
        groups = []
        products = services.products.search_products(user_id, query, MAX_RESULTS)
        if products:
            groups.append(
                (
                    "Моя аптечка",
                    [
                        (p.name, self._product_caption(p), Target(PRODUCT, p.id))
                        for p in products
                    ],
                )
            )
            groups.append(
                (
                    "Карточка товара",
                    [
                        (
                            p.name,
                            "Открыть карточку: " + p.category_name,
                            Target(CARD, p.id),
                        )
                        for p in products
                    ],
                )
            )
        shopping = services.shopping.search_items(user_id, query, MAX_RESULTS)
        if shopping:
            groups.append(
                (
                    "Список покупок",
                    [
                        (i.name, self._shopping_caption(i), Target(SHOPPING, i.id))
                        for i in shopping
                    ],
                )
            )
        notifications = services.notifications.search(user_id, query, MAX_RESULTS)
        if notifications:
            groups.append(
                (
                    "Уведомления",
                    [
                        (
                            KIND_LABELS.get(n.kind, "Уведомление"),
                            n.message,
                            Target(NOTIFICATION, n.id),
                        )
                        for n in notifications
                    ],
                )
            )
        records = services.history.search(user_id, query, MAX_RESULTS)
        if records:
            groups.append(
                (
                    "История",
                    [
                        (
                            ACTION_LABELS.get(r.action, "Действие"),
                            f"{r.description} · {r.created_at[:16]}",
                            Target(HISTORY, query),
                        )
                        for r in records
                    ],
                )
            )
        entries = search_sections(query, MAX_RESULTS)
        if entries:
            groups.append(
                (SECTIONS_TITLE, [(e.title, e.path, e.target) for e in entries])
            )
        return groups

    @staticmethod
    def _shopping_caption(item) -> str:
        state = "куплено" if item.is_bought else "нужно купить"
        return (
            f"{format_quantity(item.quantity)} {item.unit} · {state}"
            f" · {SOURCE_LABELS.get(item.source, '')}"
        )

    def _fit_height(self) -> None:
        """Высота списка по содержимому, но не больше места в окне."""
        try:
            self._results.invalidate()
            content = self._results.sizeHint().height()
            room = max(self._app.height() - MODAL_MARGIN, MIN_LIST_HEIGHT)
            self._scroll.setFixedHeight(min(content + 8, room, MAX_LIST_HEIGHT))
            self._scroll.verticalScrollBar().setValue(0)
        except RuntimeError:  # окно уже закрыто
            pass

    @staticmethod
    def _product_caption(product: Product) -> str:
        text = (
            f"{product.category_name} · {format_quantity(product.quantity)}"
            f" {product.unit}"
        )
        if product.note:
            text += f" · {product.note}"
        return text

    def _message(self, text: str) -> None:
        message = label(text, "body", "ink_3")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pad(message, 0, 24, 0, 16)
        self.message = message
        self._results.addWidget(message)

    def _group(self, title: str) -> None:
        self.group_titles.append(title)
        heading = label(title, "small_medium", "ink_3")
        pad(heading, 12, 10, 0, 4)
        self._results.addWidget(heading)

    def _add_entry(self, entry: SearchEntry) -> None:
        self._add(entry.title, entry.path, entry.target)

    def _add(self, title: str, caption: str, target: Target) -> None:
        row = _ResultRow(title, caption, target, self.choose)
        self.rows.append(row)
        self._results.addWidget(row)

    # --- выбор ---

    def _set_active(self, index: int) -> None:
        if not self.rows:
            self.active_index = -1
            return
        self.active_index = index % len(self.rows)
        for number, row in enumerate(self.rows):
            row.set_active(number == self.active_index)

    def open_active(self) -> None:
        """Открывает выбранный результат (по Enter: самый верхний)."""
        if 0 <= self.active_index < len(self.rows):
            self.choose(self.rows[self.active_index].target)

    def choose(self, target: Target) -> None:
        """Закрывает окно и переходит к найденному."""
        self.close_modal()
        self._app.go_to(target)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Стрелки вверх и вниз в поле двигают выбор по результатам."""
        if (
            watched is self.field.entry
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down)
            and self.rows
        ):
            step = 1 if event.key() == Qt.Key.Key_Down else -1
            self._set_active(max(self.active_index, 0) + step)
            return True
        return super().eventFilter(watched, event)


def open_search(app: "App", services, user_id: int) -> Optional[SearchModal]:
    """Открывает окно поиска."""
    return SearchModal(app, services, user_id)
