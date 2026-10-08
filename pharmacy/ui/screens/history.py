"""Экран «История» (макет Figma, экран 12): действия, сгруппированные по дням."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from pharmacy.models import HistoryRecord
from pharmacy.ui.fonts import line_height
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.dialog import Dialog
from pharmacy.ui.widgets.common import Line, clear_layout, label, pad
from pharmacy.ui.widgets.field import TextField
from pharmacy.ui.widgets.iconbox import IconBox
from pharmacy.ui.widgets.page import PageHeader
from pharmacy.ui.widgets.select import Select
from pharmacy.services.history_service import ACTION_LABELS
from pharmacy.ui import labels, periods
from pharmacy.ui.theme import SHADOW_PAD
from pharmacy.utils.dates import format_user_date

if TYPE_CHECKING:
    from pharmacy.ui.screens.shell import MainShell

SEARCH_WIDTH = 200
SEARCH_DELAY_MS = 250
RECORD_LIMIT = 300
PADDING_X = 22
TIME_WIDTH = 42
EMPTY_TEXT = "Записей нет"


def day_title(day: date, today: Optional[date] = None) -> str:
    """Заголовок дня: «Сегодня, 01.10.2026» или просто дата."""
    text = format_user_date(day)
    if day == (today or date.today()):
        return f"Сегодня, {text}"
    return text


def group_by_day(records: List[HistoryRecord]) -> Dict[date, List[HistoryRecord]]:
    """Раскладывает записи по дням, сохраняя порядок (новые дни и записи первыми)."""
    groups: Dict[date, List[HistoryRecord]] = {}
    for record in records:
        day = datetime.strptime(record.created_at[:10], "%Y-%m-%d").date()
        groups.setdefault(day, []).append(record)
    return groups


class HistoryScreen(QWidget):
    """Лента действий с поиском по товару и фильтрами по действию и периоду."""

    def __init__(self, shell: "MainShell") -> None:
        super().__init__()
        self._shell = shell
        self._services = shell.services
        self._user = shell.user
        self._query = ""
        self._action: Optional[str] = None
        self._period = periods.WEEK
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SEARCH_DELAY_MS)
        self._timer.timeout.connect(self._apply_search)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = PageHeader("История")
        gap = 8 - 2 * SHADOW_PAD
        self._search = TextField(
            placeholder="Поиск по товару…",
            leading_icon="search",
            compact=True,
            width=SEARCH_WIDTH,
            on_change=self._on_search,
        )
        actions = [(None, "Все действия")] + list(ACTION_LABELS.items())
        self.action_select = Select(
            actions, None, compact=True, on_change=self._on_action
        )
        self.period_select = Select(
            periods.PERIODS, self._period, compact=True, on_change=self._on_period
        )
        for widget in (self._search, self.action_select, self.period_select):
            header.actions.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)
            header.actions.addSpacing(gap)
        self.clear_button = Button(
            "Очистить историю", self._confirm_clear, variant="danger"
        )
        header.actions.addWidget(self.clear_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(header)
        self._card = Card()
        self._list = QVBoxLayout()
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(0)
        self._card.body.addLayout(self._list)
        layout.addWidget(self._card)
        layout.addStretch(1)
        self._reload()

    # --- данные ---

    @property
    def event_rows(self) -> List[QWidget]:
        """Строки событий сверху вниз."""
        return self._events

    @property
    def day_titles(self) -> List[str]:
        """Заголовки дней сверху вниз."""
        return self._titles

    def _records(self) -> List[HistoryRecord]:
        records = self._services.history.list_history(
            self._user.id,
            action=self._action,
            since=periods.since(self._period),
            limit=RECORD_LIMIT,
        )
        if self._query:
            needle = self._query.casefold()
            records = [r for r in records if needle in r.description.casefold()]
        return records

    def _reload(self) -> None:
        self._events: List[QWidget] = []
        self._titles: List[str] = []
        self.setUpdatesEnabled(False)
        try:
            clear_layout(self._list)
            groups = group_by_day(self._records())
            self.clear_button.setEnabled(
                bool(self._services.history.list_history(self._user.id, limit=1))
            )
            if not groups:
                message = label(EMPTY_TEXT, "body", "ink_3")
                message.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pad(message, 0, 40, 0, 40)
                self._list.addWidget(message)
                return
            for day, records in groups.items():
                self._day(day)
                for index, record in enumerate(records):
                    if index:
                        self._separator()
                    self._event(record)
        finally:
            self.setUpdatesEnabled(True)

    def _separator(self) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(
            PADDING_X - self._card.inner_inset, 0, PADDING_X - self._card.inner_inset, 0
        )
        row.addWidget(Line("line_soft"))
        self._list.addLayout(row)

    def _day(self, day: date) -> None:
        title = day_title(day)
        self._titles.append(title)
        text = label(title, "small_medium", "ink_3")
        pad(text, PADDING_X - self._card.inner_inset, 12, 0, 4)
        self._list.addWidget(text)

    def _event(self, record: HistoryRecord) -> None:
        row = QWidget()
        layout = QHBoxLayout(row)
        side = PADDING_X - self._card.inner_inset
        layout.setContentsMargins(side, 7, side, 7)
        layout.setSpacing(0)
        clock = label(record.created_at[11:16], "small", "ink_3")
        clock.setFixedSize(TIME_WIDTH, line_height("small"))
        clock.setContentsMargins(2, 0, 2, 0)
        layout.addWidget(clock)
        layout.addSpacing(14 - SHADOW_PAD)
        layout.addWidget(
            IconBox(
                labels.HISTORY_ICONS[record.action],
                labels.HISTORY_TONES[record.action],
                "sm",
            )
        )
        layout.addSpacing(14)
        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(2)
        texts.addWidget(label(ACTION_LABELS[record.action], "strong", tight=True))
        texts.addWidget(label(record.description, "small", "ink_2", tight=True))
        layout.addLayout(texts, 1)
        self._events.append(row)
        self._list.addWidget(row)

    # --- события ---

    def _confirm_clear(self) -> None:
        Dialog(
            self._shell.app,
            "Очистить историю?",
            "Все записи истории будут удалены без возможности восстановления. "
            "Товары и список покупок не изменятся.",
            "Очистить",
            self._clear,
            confirm_variant="danger_solid",
            warning=True,
        )

    def _clear(self) -> None:
        self._services.history.clear(self._user.id)
        self._reload()

    def _on_search(self) -> None:
        self._timer.start()

    def _apply_search(self) -> None:
        self._query = self._search.get().strip()
        self._reload()

    def _on_action(self, value: object) -> None:
        self._action = value
        self._reload()

    def _on_period(self, value: object) -> None:
        self._period = value
        self._reload()
