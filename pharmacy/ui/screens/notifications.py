"""Экран «Уведомления» (макет Figma, экран 11)."""

from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.models import Notification, NotificationKind
from pharmacy.ui.fonts import line_height
from pharmacy.ui.icons import icon_pixmap
from pharmacy.ui.paint import begin, fill_rounded
from pharmacy.ui.widgets.badge import Badge, measure_badge
from pharmacy.ui.widgets.button import Button, button_height, measure_button
from pharmacy.ui.screens.listscreen import ScrollListScreen
from pharmacy.ui.widgets.common import (
    Line,
    clear_layout,
    clickable,
    empty_message,
    label,
)
from pharmacy.ui.widgets.controls import Segmented
from pharmacy.ui.widgets.highlight import Highlight
from pharmacy.ui.widgets.iconbox import IconBox
from pharmacy.ui.widgets.page import PageHeader
from pharmacy.ui.widgets.select import Select
from pharmacy.services.notification_service import KIND_LABELS
from pharmacy.ui import labels, periods
from pharmacy.ui.theme import CARD_SHADOW_PAD, SHADOW_PAD, palette
from pharmacy.utils.dates import format_user_date

if TYPE_CHECKING:
    from pharmacy.ui.screens.shell import MainShell

# Вкладки: (подпись, вид уведомления или None, только непрочитанные).
TABS = (
    ("Все", None, False),
    ("Непрочитанные", None, True),
    ("Срок годности", "expiry", False),
    ("Низкий остаток", NotificationKind.LOW_STOCK, False),
)
EXPIRY_KINDS = (NotificationKind.EXPIRED, NotificationKind.EXPIRING)
ROW_PADDING_X = 18
ROW_PADDING_Y = 9
WHEN_WIDTH = 100
ADD_TO_LIST_TEXT = "В список покупок"
IN_LIST_TEXT = "В списке покупок"
DOT = 6
CLOSE_ICON = 15
EMPTY_TEXT = "Уведомлений нет"


def _when(created_at: str, today: Optional[date] = None) -> str:
    """Время уведомления: «сегодня, 09:00» или дата."""
    created = datetime.strptime(created_at[:19], "%Y-%m-%d %H:%M:%S")
    if created.date() == (today or date.today()):
        return f"сегодня, {created:%H:%M}"
    return format_user_date(created.date())


class _Dot(QWidget):
    """Точка слева у непрочитанного уведомления."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedSize(DOT, DOT)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        begin(painter)
        fill_rounded(painter, QRectF(0, 0, DOT, DOT), DOT / 2, palette().primary)


class _Row(Highlight):
    """Строка уведомления: подложка, а у непрочитанного ещё и точка слева."""

    def __init__(self, color: str, unread: bool) -> None:
        super().__init__(color)
        self._dot = _Dot(self) if unread else None

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._dot is not None:
            self._dot.move(self.padding_x, (self.height() - DOT) // 2)


class NotificationsScreen(ScrollListScreen):
    """Список уведомлений с вкладками, периодом и действиями."""

    def __init__(self, shell: "MainShell") -> None:
        super().__init__(shell)
        self._tab = 0
        self._rows = {}
        self._measure_actions()
        self._period = periods.ALL_TIME
        header = PageHeader("Уведомления")
        self.period_select = Select(
            periods.PERIODS, self._period, compact=True, on_change=self._on_period
        )
        header.actions.addWidget(self.period_select)
        header.actions.addSpacing(8 - 2 * SHADOW_PAD)
        self.read_all_button = Button("Прочитать все", command=self._read_all)
        header.actions.addWidget(self.read_all_button)
        self._layout.addWidget(header)
        self._layout.addLayout(self._build_tabs())
        self._add_list_card()
        self._reload()

    # --- вкладки ---

    def _build_tabs(self) -> QHBoxLayout:
        row = QHBoxLayout()
        gap = 12 - SHADOW_PAD
        row.setContentsMargins(CARD_SHADOW_PAD - SHADOW_PAD, gap, CARD_SHADOW_PAD, gap)
        row.setSpacing(0)
        self._tabs = Segmented(self._tab_labels(), self._tab, self._on_tab)
        row.addWidget(self._tabs)
        row.addStretch(1)
        days = self._user.warning_days
        hint = f"Предупреждение о сроке — за {days} дн. (меняется в Настройках)"
        row.addWidget(label(hint, "small", "ink_3"))
        return row

    def _tab_labels(self) -> List[str]:
        items = self._period_items()
        unread = sum(1 for item in items if not item.is_read)
        return [
            f"Все · {len(items)}",
            f"Непрочитанные · {unread}",
            TABS[2][0],
            TABS[3][0],
        ]

    # --- данные ---

    @property
    def tabs(self) -> Segmented:
        """Вкладки-фильтры."""
        return self._tabs

    @property
    def rows(self) -> List[QWidget]:
        """Строки показанных уведомлений сверху вниз."""
        return [
            self._list.itemAt(i).widget()
            for i in range(self._list.count())
            if isinstance(self._list.itemAt(i).widget(), _Row)
        ]

    def _period_items(self) -> List[Notification]:
        return self._services.notifications.list_notifications(
            self._user.id, since=periods.since(self._period)
        )

    def _visible(self) -> List[Notification]:
        _label, kind, unread_only = TABS[self._tab]
        kinds = EXPIRY_KINDS if kind == "expiry" else (kind,)
        return [
            item
            for item in self._period_items()
            if (item.kind in kinds or kind is None)
            and (not item.is_read or not unread_only)
        ]

    def reveal(self, notification_id: int) -> None:
        """Показывает все уведомления и прокручивает список к нужному."""
        self._tab = 0
        self._period = periods.ALL_TIME
        self.period_select.set(self._period)
        self._tabs.select(0)
        self._reload()
        row = self._rows.get(notification_id)
        if row is not None:
            QTimer.singleShot(0, lambda: self._scroll.ensureWidgetVisible(row))

    def _reload(self) -> None:
        """Перерисовывает вкладки и список и обновляет счётчик в меню."""
        QTimer.singleShot(40, self.fit_rows)  # после того, как строки покажутся
        self.setUpdatesEnabled(False)
        try:
            self._tabs.set_items(self._tab_labels())
            clear_layout(self._list)
            self._rows = {}
            items = self._visible()
            if not items:
                self._list.addWidget(empty_message(EMPTY_TEXT))
            for index, item in enumerate(items):
                if index:
                    self._list.addWidget(Line("line"))
                row = self._row(item)
                self._rows[item.id] = row
                self._list.addWidget(row)
        finally:
            self.setUpdatesEnabled(True)
        self._shell.refresh_counters()

    # --- строка ---

    def _row(self, item: Notification) -> QWidget:
        pal = palette()
        background = pal.card if item.is_read else pal.unread_bg
        # Подсветка непрочитанного: скруглённая плашка, а не прямоугольник у края
        # карточки. У прочитанных строк плашка того же цвета, что карточка, поэтому
        # размеры строк одинаковые.
        row = _Row(background, not item.is_read)
        inner = QHBoxLayout()
        side = ROW_PADDING_X - self._card.inner_inset - SHADOW_PAD - row.padding_x + 4
        inner.setContentsMargins(
            side, ROW_PADDING_Y - row.padding_y, side, ROW_PADDING_Y - row.padding_y
        )
        inner.setSpacing(0)
        inner.addSpacing(SHADOW_PAD)
        inner.addWidget(
            IconBox(
                labels.NOTIFICATION_ICONS[item.kind],
                labels.NOTIFICATION_TONES[item.kind],
            )
        )
        inner.addSpacing(14)
        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(0)
        texts.addWidget(label(KIND_LABELS[item.kind], "strong", tight=True))
        texts.addSpacing(3)
        texts.addWidget(label(item.message, "small", "ink_2", tight=True))
        inner.addLayout(texts, 1)
        inner.addSpacing(8)
        when = label(_when(item.created_at), "caption", "ink_3")
        when.setFixedSize(WHEN_WIDTH, line_height("caption"))
        when.setContentsMargins(2, 0, 2, 0)
        when.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        inner.addWidget(when)
        inner.addSpacing(8)
        inner.addWidget(self._actions(item))
        inner.addSpacing(8)
        inner.addWidget(self._close_icon(item))
        row.body.addLayout(inner)
        return row

    def _close_icon(self, item: Notification) -> QLabel:
        close = QLabel()
        close.setPixmap(icon_pixmap("x", CLOSE_ICON, palette().ink_3))
        close.setFixedSize(CLOSE_ICON, CLOSE_ICON)
        clickable(close, lambda i=item.id: self._delete(i))
        return close

    def _actions(self, item: Notification) -> QWidget:
        # Два столбца фиксированной ширины: «Открыть товар» и «В список покупок»
        # (или плашка «В списке покупок»). У всех строк они стоят ровно друг под другом.
        height = button_height("sm") + 2 * SHADOW_PAD
        box = QWidget()
        box.setFixedSize(self._actions_width, height)
        row = QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(
            Button(
                "Открыть товар",
                command=lambda: self._open_product(item),
                size="sm",
                width=self._open_width,
            )
        )
        slot = QWidget()
        slot.setFixedSize(self._list_width + 2 * SHADOW_PAD, height)
        slot_row = QHBoxLayout(slot)
        slot_row.setContentsMargins(0, 0, 0, 0)
        slot_row.setSpacing(0)
        if self._services.shopping.is_in_list(self._user.id, item.product_id):
            slot_row.addSpacing(SHADOW_PAD)
            slot_row.addWidget(Badge(IN_LIST_TEXT, "green", icon="check"))
            slot_row.addStretch(1)
        else:
            slot_row.addWidget(
                Button(
                    ADD_TO_LIST_TEXT,
                    command=lambda: self._add_to_list(item),
                    variant="primary",
                    size="sm",
                    icon="plus",
                    width=self._list_width,
                )
            )
        row.addWidget(slot)
        return box

    def _measure_actions(self) -> None:
        """Считает ширину столбцов кнопок: по самому широкому содержимому."""
        self._open_width = measure_button("Открыть товар", "sm")
        self._list_width = max(
            measure_button(ADD_TO_LIST_TEXT, "sm", "plus"),
            measure_badge(IN_LIST_TEXT, "check"),
        )
        self._actions_width = self._open_width + self._list_width + 4 * SHADOW_PAD

    # --- действия ---

    def _on_tab(self, index: int) -> None:
        self._tab = index
        self._reload()

    def _on_period(self, value: object) -> None:
        self._period = value
        self._reload()

    def _read_all(self) -> None:
        self._services.notifications.mark_all_read(self._user.id)
        self._reload()

    def _mark_read(self, item: Notification) -> None:
        try:
            self._services.notifications.mark_read(self._user.id, item.id)
        except NotFoundError:
            pass

    def _open_product(self, item: Notification) -> None:
        self._mark_read(item)
        self._reload()  # точка «непрочитано» исчезает под открывшейся карточкой
        self._shell.open_product(item.product_id)

    def _add_to_list(self, item: Notification) -> None:
        self._mark_read(item)
        try:
            self._services.shopping.add_from_product(self._user.id, item.product_id)
        except (NotFoundError, ValidationError):
            pass
        self._reload()

    def _delete(self, notification_id: int) -> None:
        try:
            self._services.notifications.delete(self._user.id, notification_id)
        except NotFoundError:
            pass
        self._reload()
