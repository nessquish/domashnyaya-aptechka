"""Основа экранов «История» и «Уведомления»: карточка с листающимся списком."""

from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from pharmacy.ui.paging import fit_scroll
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.scroll import ScrollArea

if TYPE_CHECKING:
    from pharmacy.ui.screens.shell import MainShell


class ScrollListScreen(QWidget):
    """Экран, где шапка и кнопки стоят на месте, а листается только список."""

    def __init__(self, shell: "MainShell") -> None:
        super().__init__()
        self._shell = shell
        self._services = shell.services
        self._user = shell.user
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

    def _add_list_card(self) -> None:
        """Кладёт на экран карточку со списком (в ``self._list``) и растяжку."""
        self._card = Card()
        self._scroll = ScrollArea(gutter=8)
        self._list = self._scroll.body
        self._card.body.addWidget(self._scroll)
        self._layout.addWidget(self._card)
        self._layout.addStretch(1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.fit_rows)

    def fit_rows(self) -> None:
        """Подгоняет высоту списка под окно (вызывается и при смене размера окна)."""
        try:
            fit_scroll(self, self._card, self._scroll, self._shell.viewport_height())
        except RuntimeError:  # экран уже закрыт
            pass
