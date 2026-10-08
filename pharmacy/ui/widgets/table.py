"""Таблица из макета: шапка с сортировкой и строки с разделителями."""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QWidget

from pharmacy.ui.fonts import line_height
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.common import clickable, label, pad
from pharmacy.ui.theme import palette

HEADER_PADDING_Y = 10
CELL_PADDING_X = 12
CELL_PADDING_Y = 9
SORT_ICON = 12
SORT_GAP = 4
SELECT_WIDTH = 44  # столбец с флажками, если таблица с выбором строк


@dataclass(frozen=True)
class Column:
    """Столбец таблицы.

    Attributes:
        title: Заголовок.
        weight: Относительная ширина столбца.
        fixed: Ширина в пикселях вместо относительной (например, у флажков).
    """

    title: str
    weight: int = 1
    fixed: Optional[int] = None


@dataclass(frozen=True)
class TextCell:
    """Текстовая ячейка.

    Attributes:
        text: Текст.
        color: Роль цвета: ``ink``, ``ink_2``, ``ink_3`` или ``primary``.
        bold: Полужирный шрифт.
        strike: Зачёркнутый текст (купленные позиции).
        on_click: Если задано, ячейка работает как ссылка.
    """

    text: str
    color: str = "ink"
    bold: bool = False
    strike: bool = False
    on_click: Optional[Callable[[], None]] = None


Cell = Union[str, TextCell, Callable[[], QWidget]]


class _Fill(QWidget):
    """Однотонная полоса: подложка выбранной строки или разделитель."""

    def __init__(self, color: str, height: Optional[int] = None) -> None:
        super().__init__()
        self._color = color
        self.backdrop_color = color
        if height is not None:
            self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)


class _Table(QWidget):
    """Сетка таблицы: сама красит шапку, если её не красит карточка."""

    def __init__(self, header_height: int) -> None:
        super().__init__()
        self._header_height = header_height
        self.paint_header = False

    def paintEvent(self, _event) -> None:
        if self.paint_header:
            painter = QPainter(self)
            painter.fillRect(
                0, 0, self.width(), self._header_height, palette().table_head
            )


class DataTable(QWidget):
    """Шапка и строки таблицы. Столбцы делят ширину пропорционально весам."""

    def __init__(
        self,
        columns: Sequence[Column],
        card: Optional[Card] = None,
        parent: Optional[QWidget] = None,
        selectable: bool = False,
    ) -> None:
        """Создаёт таблицу без строк.

        Args:
            columns: Столбцы слева направо.
            card: Карточка, в которую вставлена таблица. Она красит шапку
                вместе со скруглёнными верхними углами.
            parent: Родитель.
            selectable: Добавить слева столбец с флажками. Номера столбцов в
                методах таблицы при этом остаются прежними: флажки считаются
                отдельно (флажок в шапке: ``set_header_widget(-1, ...)``).
        """
        super().__init__(parent)
        self._card = card
        self._offset = 1 if selectable else 0
        self._columns = ([Column("", fixed=SELECT_WIDTH)] if selectable else []) + list(
            columns
        )
        self._fills: Dict[int, QWidget] = {}
        self._caption_column: Optional[int] = None
        self._caption = ""
        self._header_clicks: Dict[int, Callable[[], None]] = {}
        self._header_tips: Dict[int, str] = {}
        self._rounded_top = True
        self._header_widgets: Dict[int, QWidget] = {}
        self._header_height = line_height("body_medium") + 2 * HEADER_PADDING_Y
        self._rows: List[QWidget] = []
        self._cells: List[List[QWidget]] = []
        self._next_row = 1
        self._data_rows = 0
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self._grid_host = _Table(self._header_height)
        outer.addWidget(self._grid_host)
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(0)
        self._header_cells: List[QWidget] = []
        for index, column in enumerate(self._columns):
            if column.fixed is not None:
                self._grid.setColumnMinimumWidth(index, column.fixed)
                self._grid.setColumnStretch(index, 0)
            else:
                self._grid.setColumnStretch(index, column.weight)
        self._grid.setRowMinimumHeight(0, self._header_height)
        self._build_header()
        self.set_rounded_top(True)

    # --- шапка ---

    def _build_header(self) -> None:
        for cell in self._header_cells:
            cell.setParent(None)
            cell.deleteLater()
        self._header_cells = []
        for index, column in enumerate(self._columns):
            self._header_cells.append(self._header_cell(index, column))
            self._grid.addWidget(self._header_cells[-1], 0, index)

    def _header_cell(self, index: int, column: Column) -> QWidget:
        cell = self._wrap(None, column, HEADER_PADDING_Y)
        layout = cell.layout()
        widget = self._header_widgets.get(index)
        if widget is not None:
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
            return cell
        layout.addWidget(
            label(column.title, "body_medium", "ink_2", bare=True),
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        if index == self._caption_column and self._caption:
            layout.addSpacing(SORT_GAP)
            layout.addWidget(
                label(self._caption, "small_medium", "primary", bare=True),
                0,
                Qt.AlignmentFlag.AlignVCenter,
            )
        layout.addStretch(1)
        if index in self._header_clicks:
            clickable(cell, self._header_clicks[index])
        if self._header_tips.get(index):
            cell.setToolTip(self._header_tips[index])
        return cell

    def set_sort_caption(self, index: Optional[int], text: str = "") -> None:
        """Показывает фиолетовую подпись сортировки рядом с заголовком столбца.

        Подпись есть только у столбца, по которому таблица отсортирована сейчас
        («А-Я», «9-0» ...). None убирает подпись.

        Args:
            index: Номер столбца.
            text: Короткая подпись.
        """
        self._caption_column = None if index is None else index + self._offset
        self._caption = text
        self._build_header()

    def set_header_click(
        self, index: int, command: Callable[[], None], tip: str = ""
    ) -> None:
        """Делает заголовок столбца нажимаемым (например, чтобы менять сортировку).

        Args:
            index: Номер столбца.
            command: Что вызвать при нажатии на заголовок.
            tip: Подсказка при наведении.
        """
        index += self._offset
        self._header_clicks[index] = command
        self._header_tips[index] = tip
        self._build_header()

    def set_header_tip(self, index: int, tip: str) -> None:
        """Меняет подсказку заголовка столбца."""
        index += self._offset
        self._header_tips[index] = tip
        if index < len(self._header_cells):
            self._header_cells[index].setToolTip(tip)

    def set_rounded_top(self, rounded: bool) -> None:
        """Красит шапку у верхнего края карточки.

        Выключается, когда над таблицей стоит панель действий.
        """
        self._rounded_top = rounded
        if self._card is not None and rounded:
            self._card.set_band(self._header_height, palette().table_head)
        elif self._card is not None:
            self._card.set_band(0, None)
        self._grid_host.paint_header = not (rounded and self._card is not None)
        self._grid_host.update()

    def set_header_widget(self, index: int, factory: Callable[[], QWidget]) -> QWidget:
        """Кладёт виджет в шапку вместо заголовка столбца (общий флажок).

        Args:
            index: Номер столбца.
            factory: Создаёт виджет.

        Returns:
            Созданный виджет.
        """
        widget = factory()
        self._header_widgets[index + self._offset] = widget
        self._build_header()
        return widget

    # --- строки ---

    def clear(self) -> None:
        """Удаляет все строки."""
        for widget in self._rows:
            self._grid.removeWidget(widget)
            widget.setParent(None)
            widget.deleteLater()
        self._rows = []
        self._cells = []
        self._fills = {}
        self._next_row = 1
        self._data_rows = 0

    def _add(self, widget: QWidget, row: int, column: int, span: int = 1) -> None:
        self._grid.addWidget(widget, row, column, 1, span)
        self._rows.append(widget)

    def _separator(self) -> None:
        self._add(_Fill(palette().line, 1), self._next_row, 0, len(self._columns))
        self._next_row += 1

    def add_row(
        self,
        cells: Sequence[Cell],
        selected: bool = False,
        check: Optional[Callable[[], QWidget]] = None,
        on_click: Optional[Callable[[], None]] = None,
    ) -> None:
        """Добавляет строку.

        Args:
            cells: Содержимое ячеек по столбцам: текст, ``TextCell`` или
                функция, создающая виджет.
            selected: Подсветить строку (выбранная или непрочитанная).
            check: Создаёт флажок строки (для таблицы с ``selectable``).
            on_click: Нажатие на свободное место строки (например, выбрать её).
        """
        self._separator()
        row = self._next_row
        self._next_row += 1
        if self._offset:
            cells = [check or ""] + list(cells)
        if selected:
            self.set_row_selected(self._data_rows, True, row)
        self._data_rows += 1
        wrappers = []
        for index, cell in enumerate(cells):
            wrapper = self._make_cell(cell, self._columns[index])
            if on_click is not None and self._columns[index].fixed is None:
                clickable(wrapper, on_click)  # столбец с флажком не в счёт
            self._add(wrapper, row, index)
            wrappers.append(wrapper)
        self._cells.append(wrappers)

    def set_row_selected(
        self, index: int, selected: bool, grid_row: Optional[int] = None
    ) -> None:
        """Подсвечивает или снимает подсветку строки, не перестраивая таблицу.

        Args:
            index: Номер строки с данными (с нуля).
            selected: Подсветить или снять подсветку.
            grid_row: Строка сетки (только при добавлении строки).
        """
        fill = self._fills.get(index)
        if not selected:
            if fill is not None:
                del self._fills[index]
                self._rows.remove(fill)
                self._grid.removeWidget(fill)
                fill.setParent(None)
                fill.deleteLater()
            return
        if fill is not None:
            return
        if grid_row is None:
            grid_row = 2 + 2 * index  # разделитель и строка идут парами
        fill = _Fill(palette().unread_bg)
        self._fills[index] = fill
        self._add(fill, grid_row, 0, len(self._columns))
        fill.lower()

    def add_message(self, text: str) -> None:
        """Добавляет строку с сообщением на всю ширину («Ничего не найдено»)."""
        self._separator()
        message = label(text, "body", "ink_3")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pad(message, 0, 36, 0, 36)
        self._add(message, self._next_row, 0, len(self._columns))
        self._next_row += 1

    @property
    def header_height(self) -> int:
        """Высота шапки таблицы."""
        return self._header_height

    @property
    def row_count(self) -> int:
        """Сколько строк с данными в таблице (без сообщений)."""
        return self._data_rows

    @property
    def row_texts(self) -> List[List[str]]:
        """Тексты ячеек всех строк (у плашки её надпись, у других виджетов пусто)."""
        rows = []
        for wrappers in self._cells:
            texts = []
            for wrapper in wrappers[self._offset :]:
                item = wrapper.layout().itemAt(0)
                content = item.widget() if item is not None else None
                if isinstance(content, QLabel):
                    texts.append(content.text())
                else:
                    value = getattr(content, "text", "")
                    texts.append(value() if callable(value) else value)
            rows.append(texts)
        return rows

    def check_widgets(self) -> List[QWidget]:
        """Флажки строк (для таблицы с ``selectable``)."""
        return [wrappers[0].layout().itemAt(0).widget() for wrappers in self._cells]

    def cell_widgets(self, column: int) -> List[QWidget]:
        """Содержимое ячеек одного столбца по строкам (виджеты, не обёртки)."""
        column += self._offset
        return [
            wrappers[column].layout().itemAt(0).widget() for wrappers in self._cells
        ]

    @property
    def caption_column(self) -> Optional[int]:
        """Столбец, рядом с заголовком которого показана подпись сортировки."""
        if self._caption_column is None:
            return None
        return self._caption_column - self._offset

    @property
    def caption(self) -> str:
        """Подпись сортировки в шапке («А-Я»)."""
        return self._caption

    def _wrap(
        self, content: Optional[QWidget], column: Column, padding_y: int
    ) -> QWidget:
        """Оборачивает содержимое ячейки: отступы и ширина по столбцу."""
        cell = QWidget()
        layout = QHBoxLayout(cell)
        layout.setContentsMargins(CELL_PADDING_X, padding_y, CELL_PADDING_X, padding_y)
        layout.setSpacing(0)
        if column.fixed is not None:
            cell.setFixedWidth(column.fixed)
        else:
            cell.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        if content is not None:
            layout.addWidget(content, 0, Qt.AlignmentFlag.AlignVCenter)
            layout.addStretch(1)
        return cell

    def _make_cell(self, cell: Cell, column: Column) -> QWidget:
        if callable(cell):
            return self._wrap(cell(), column, CELL_PADDING_Y)
        spec = TextCell(cell) if isinstance(cell, str) else cell
        text = label(
            spec.text,
            "strong" if spec.bold else "body",
            spec.color,
            strike=spec.strike,
            tight=True,
        )
        if spec.on_click is not None:
            clickable(text, spec.on_click)
        return self._wrap(text, column, CELL_PADDING_Y)
