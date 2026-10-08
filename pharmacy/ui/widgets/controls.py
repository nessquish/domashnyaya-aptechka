"""Мелкие элементы управления: вкладки, переключатели, чекбокс, пагинация."""

from typing import Callable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from pharmacy.ui.fonts import font, line_height, text_width
from pharmacy.ui.icons import icon_pixmap
from pharmacy.ui.paint import Shadow, begin, draw_shadows, fill_rounded, qcolor
from pharmacy.ui import theme
from pharmacy.ui.theme import palette

Callback = Callable[[int], None]


class Segmented(QWidget):
    """Ряд вариантов, из которых выбран один.

    Два вида из макета: ``tabs`` (вкладки на серой подложке) и ``outline``
    (рамка с выделенным вариантом, как выбор темы).
    """

    PAD = 4  # поле под тень выбранного варианта

    def __init__(
        self,
        items: Sequence[str],
        active: int = 0,
        on_change: Optional[Callback] = None,
        variant: str = "tabs",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Создаёт переключатель.

        Args:
            items: Подписи вариантов.
            active: Номер выбранного варианта.
            on_change: Вызывается с номером выбранного варианта.
            variant: ``tabs`` или ``outline``.

        Raises:
            ValueError: Если такого вида нет.
        """
        super().__init__(parent)
        if variant not in ("tabs", "outline"):
            raise ValueError(f"Неизвестный вид переключателя: {variant}")
        self._variant = variant
        self._items = list(items)
        self._active = active
        self._on_change = on_change
        self._padding_x = 12 if variant == "tabs" else 14
        self._gap = 4 if variant == "tabs" else 0
        self._edge = 3 if variant == "tabs" else 1
        self._height = line_height("small") + 12 + 2 * self._edge
        self.spans: List[Tuple[int, int]] = []
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._relayout()

    @property
    def active(self) -> int:
        """Номер выбранного варианта."""
        return self._active

    def select(self, index: int) -> None:
        """Выбирает вариант без вызова обработчика."""
        self._active = index
        self.update()

    def set_items(self, items: Sequence[str]) -> None:
        """Заменяет подписи (например, обновляет числа во вкладках)."""
        self._items = list(items)
        self._relayout()

    def _widths(self) -> List[int]:
        return [
            text_width(text, "small_medium") + 2 * self._padding_x
            for text in self._items
        ]

    def _relayout(self) -> None:
        widths = self._widths()
        total = sum(widths) + self._gap * (len(widths) - 1) + 2 * self._edge
        self.setFixedSize(total + 2 * self.PAD, self._height + 2 * self.PAD)
        self.spans = []
        left = self.PAD + self._edge
        for width in widths:
            self.spans.append((left, left + width))
            left += width + self._gap
        self.update()

    def sizeHint(self) -> QSize:
        return self.size()

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        begin(painter)
        total = self.width() - 2 * self.PAD
        base = QRectF(self.PAD, self.PAD, total, self._height)
        if self._variant == "tabs":
            fill_rounded(painter, base, 8, pal.tabs_bg)
        else:
            fill_rounded(painter, base, theme.CONTROL_RADIUS, pal.input_bg, pal.line)
        top = self.PAD + self._edge
        inner = self._height - 2 * self._edge
        for index, ((left, right), text) in enumerate(zip(self.spans, self._items)):
            chosen = index == self._active
            cell = QRectF(left, top, right - left, inner)
            if chosen:
                if self._variant == "tabs":
                    draw_shadows(painter, cell, 6, (Shadow(1, 3, pal.shadow, 0.08),))
                    fill_rounded(painter, cell, 6, pal.card)
                else:
                    fill_rounded(painter, cell, 6, pal.primary_soft)
            painter.setFont(font("small_medium" if chosen else "small"))
            painter.setPen(qcolor(pal.primary_ink if chosen else pal.ink_2))
            painter.drawText(cell, Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event) -> None:
        x = event.position().x()
        for index, (left, right) in enumerate(self.spans):
            if left <= x < right and index != self._active:
                self._active = index
                self.update()
                if self._on_change is not None:
                    self._on_change(index)
                return


class _Switch(QWidget):
    """Основа для нажимаемых переключателей с состоянием «да/нет»."""

    def __init__(
        self,
        width: int,
        height: int,
        value: bool,
        on_change: Optional[Callable[[bool], None]],
        parent: Optional[QWidget],
    ) -> None:
        super().__init__(parent)
        self._value = value
        self._on_change = on_change
        self.setFixedSize(width, height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def value(self) -> bool:
        """Включён ли переключатель."""
        return self._value

    def set(self, value: bool) -> None:
        """Меняет состояние без вызова обработчика."""
        self._value = value
        self.update()

    def sizeHint(self) -> QSize:
        return self.size()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._value = not self._value
        self.update()
        if self._on_change is not None:
            self._on_change(self._value)


class Toggle(_Switch):
    """Переключатель включено/выключено (34 на 19 пикселей)."""

    WIDTH, HEIGHT, KNOB = 34, 19, 15

    def __init__(
        self,
        value: bool = False,
        on_change: Optional[Callable[[bool], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(self.WIDTH, self.HEIGHT, value, on_change, parent)

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        begin(painter)
        track = pal.primary if self._value else pal.checkbox_line
        fill_rounded(
            painter, QRectF(0, 0, self.WIDTH, self.HEIGHT), self.HEIGHT / 2, track
        )
        inset = (self.HEIGHT - self.KNOB) / 2
        left = self.WIDTH - inset - self.KNOB if self._value else inset
        fill_rounded(
            painter, QRectF(left, inset, self.KNOB, self.KNOB), self.KNOB / 2, "#FFFFFF"
        )


class Checkbox(_Switch):
    """Флажок 14 на 14 пикселей с галочкой."""

    SIZE = 14

    def __init__(
        self,
        value: bool = False,
        on_change: Optional[Callable[[bool], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Создаёт флажок.

        Args:
            value: Отмечен ли флажок.
            on_change: Вызывается с новым состоянием после нажатия.
        """
        super().__init__(self.SIZE, self.SIZE, value, on_change, parent)

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        begin(painter)
        box = QRectF(0, 0, self.SIZE, self.SIZE)
        if self._value:
            fill_rounded(painter, box, 4, pal.primary)
            painter.drawPixmap(2, 2, icon_pixmap("check", 10, "#FFFFFF", 3.5))
        else:
            fill_rounded(painter, box, 4, pal.input_bg, pal.checkbox_line, 2)


class Slider(QWidget):
    """Ползунок: значение от минимума до максимума, тянется мышью.

    ``on_change`` вызывается при каждом движении, ``on_done`` когда кнопку
    мыши отпустили (удобно сохранять значение один раз).
    """

    WIDTH, HEIGHT = 220, 22
    TRACK, KNOB = 4, 16

    def __init__(
        self,
        minimum: int,
        maximum: int,
        value: int,
        on_change: Optional[Callable[[int], None]] = None,
        on_done: Optional[Callable[[int], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._min, self._max = minimum, maximum
        self._value = max(minimum, min(value, maximum))
        self._on_change = on_change
        self._on_done = on_done
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def value(self) -> int:
        """Текущее значение."""
        return self._value

    def set(self, value: int) -> None:
        """Меняет значение без вызова обработчиков."""
        self._value = max(self._min, min(value, self._max))
        self.update()

    def sizeHint(self) -> QSize:
        return self.size()

    def _from_x(self, x: float) -> int:
        left, right = self.KNOB / 2, self.WIDTH - self.KNOB / 2
        share = (min(max(x, left), right) - left) / (right - left)
        return round(self._min + share * (self._max - self._min))

    def _move(self, event) -> None:
        value = self._from_x(event.position().x())
        if value != self._value:
            self._value = value
            self.update()
            if self._on_change is not None:
                self._on_change(value)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._move(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._move(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_done:
            self._on_done(self._value)

    def keyPressEvent(self, event) -> None:
        step = {Qt.Key.Key_Left: -1, Qt.Key.Key_Right: 1}.get(event.key())
        if step is None:
            super().keyPressEvent(event)
            return
        self.set(self._value + step)
        if self._on_change is not None:
            self._on_change(self._value)
        if self._on_done is not None:
            self._on_done(self._value)

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        begin(painter)
        half = self.KNOB / 2
        middle = self.HEIGHT / 2
        share = (self._value - self._min) / max(self._max - self._min, 1)
        x = half + share * (self.WIDTH - self.KNOB)
        track = QRectF(
            half, middle - self.TRACK / 2, self.WIDTH - self.KNOB, self.TRACK
        )
        fill_rounded(painter, track, self.TRACK / 2, pal.checkbox_line)
        done = QRectF(half, track.top(), x - half, self.TRACK)
        fill_rounded(painter, done, self.TRACK / 2, pal.primary)
        knob = QRectF(x - half, middle - half, self.KNOB, self.KNOB)
        fill_rounded(painter, knob, half, "#FFFFFF", pal.primary, 2)


class Pagination(QWidget):
    """Кнопки страниц: стрелки и номера."""

    CELL, GAP = 24, 4

    def __init__(
        self,
        page: int,
        pages: int,
        on_change: Callback,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Создаёт пагинацию.

        Args:
            page: Номер текущей страницы (с 1).
            pages: Сколько всего страниц.
            on_change: Вызывается с номером выбранной страницы.
        """
        super().__init__(parent)
        self._page = page
        self._pages = max(pages, 1)
        self._on_change = on_change
        cells = len(self._cells())
        self.setFixedSize(cells * self.CELL + (cells - 1) * self.GAP, self.CELL)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return self.size()

    @property
    def page(self) -> int:
        """Номер текущей страницы."""
        return self._page

    def _cells(self) -> List[Tuple[str, int]]:
        numbers = [("page", n) for n in range(1, self._pages + 1)]
        return [("prev", self._page - 1)] + numbers + [("next", self._page + 1)]

    def cell_left(self, index: int) -> int:
        """Левый край ячейки по порядку (0 это стрелка «назад»)."""
        return index * (self.CELL + self.GAP)

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        begin(painter)
        for index, (kind, target) in enumerate(self._cells()):
            cell = QRectF(self.cell_left(index), 0, self.CELL, self.CELL)
            current = kind == "page" and target == self._page
            enabled = 1 <= target <= self._pages
            if current:
                fill_rounded(painter, cell, 6, pal.primary, pal.primary)
            else:
                fill_rounded(painter, cell, 6, pal.input_bg, pal.line)
            if kind == "page":
                painter.setFont(font("small"))
                painter.setPen(qcolor(pal.on_primary if current else pal.ink_2))
                painter.drawText(cell, Qt.AlignmentFlag.AlignCenter, str(target))
            else:
                name = "chevron-left" if kind == "prev" else "chevron-right"
                color = pal.ink_2 if enabled else pal.checkbox_line
                painter.drawPixmap(
                    round(cell.center().x() - 7),
                    round(cell.center().y() - 7),
                    icon_pixmap(name, 14, color),
                )

    def mousePressEvent(self, event) -> None:
        x = event.position().x()
        for index, (kind, target) in enumerate(self._cells()):
            left = self.cell_left(index)
            enabled = 1 <= target <= self._pages
            if left <= x < left + self.CELL and enabled and target != self._page:
                self._page = target
                self.update()
                self._on_change(target)
                return
