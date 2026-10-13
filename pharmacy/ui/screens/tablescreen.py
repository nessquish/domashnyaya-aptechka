"""Основа экранов с постраничной таблицей: «Моя аптечка» и «Список покупок»."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget

from pharmacy.ui.paging import fitted_rows
from pharmacy.ui.widgets.actionbar import HEIGHT as BAR_HEIGHT


class PagedTableScreen(QWidget):
    """Таблица занимает окно до низа: число строк на странице подгоняется под него.

    Наследник хранит ``_card``, ``_table``, ``_bar``, ``_footer``, ``_page``,
    ``_page_size``, ``_shell``, ``PAGING_KEY`` и умеет ``_reload``.
    """

    PAGING_KEY = ""

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.fit_rows)

    def fit_rows(self) -> None:
        """Подгоняет число строк на странице под высоту окна."""
        if not hasattr(self, "_footer"):  # таблица ещё не построена
            return
        size = fitted_rows(
            self.PAGING_KEY,
            self,
            self._card,
            self._table,
            self._table.header_height,
            self._table.row_count,
            self._page_size,
            self._shell.viewport_height(),
            0 if self._bar.isVisible() else BAR_HEIGHT,
        )
        if size != self._page_size:
            first = (self._page - 1) * self._page_size
            self._page_size = size
            self._page = first // size + 1
            self._reload()
            QTimer.singleShot(0, self.fit_rows)

    def _on_page(self, page: int) -> None:
        self._page = page
        self._reload()
