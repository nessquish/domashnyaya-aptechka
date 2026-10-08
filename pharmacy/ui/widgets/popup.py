"""Всплывающий список вариантов под полем (выпадающий список)."""

from typing import Callable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QWidget

from pharmacy.ui.fonts import font, text_width
from pharmacy.ui.paint import Shadow, begin, draw_shadows, fill_rounded, qcolor
from pharmacy.ui.theme import mix, palette

Option = Tuple[object, str]  # (значение, подпись)
# Следующая ступень выбора: (варианты, выделенное значение, что вызвать при выборе,
# что вызвать для ещё одной ступени).
Stage = Tuple[
    Sequence[Option],
    object,
    Callable[[object], None],
    Optional[Callable[[object], Optional[Tuple]]],
]

ITEM_HEIGHT = 30
ITEM_PADDING_X = 12
LIST_PADDING = 4
SHADOW_PAD = 12
MAX_VISIBLE = 8
LIST_RADIUS = 8
TOP_PAD = 2  # отступ списка от нижнего края поля


class PopupList(QWidget):
    """Список вариантов поверх содержимого окна приложения.

    Это не отдельное окно, а обычный виджет внутри главного: он двигается,
    сворачивается и закрывается вместе с ним и не остаётся поверх других
    программ. Закрывается по выбору варианта, по Esc, по нажатию вне списка и
    при изменении размера окна. Длинный список прокручивается колёсиком мыши.
    Если снизу не хватает места, открывается над полем.
    """

    def __init__(
        self,
        anchor: QWidget,
        options: Sequence[Option],
        selected: object,
        on_pick: Callable[[object], None],
        on_close: Optional[Callable[[], None]] = None,
        field_rect: Optional[QRectF] = None,
        on_stage: Optional[Callable[[object], Optional[Stage]]] = None,
        take_focus: bool = True,
    ) -> None:
        """Открывает список под полем.

        Args:
            anchor: Поле, под которым появляется список.
            options: Варианты (значение, подпись).
            selected: Значение выбранного варианта (выделяется жирным).
            on_pick: Вызывается со значением выбранного варианта.
            on_close: Вызывается при закрытии списка.
            field_rect: Видимая рамка поля внутри anchor (по умолчанию весь anchor).
            on_stage: Для списка из двух ступеней (вид сортировки, затем подвид).
                Вызывается с выбранным значением; если вернула следующую ступень,
                список в том же окне меняется на неё и остаётся открытым.
            take_focus: False для подсказок при вводе: фокус остаётся в поле,
                и можно продолжать печатать.
        """
        self._window = anchor.window()
        super().__init__(self._window)
        self._anchor = anchor
        self._choices: List[Option] = list(options)
        self._selected = selected
        self._on_pick = on_pick
        self._on_stage = on_stage
        self._on_close = on_close
        self._hover = -1
        self._offset = 0
        self._closed = False
        self._box = field_rect or QRectF(anchor.rect())
        self._fit()
        self.setMouseTracking(True)
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus if take_focus else Qt.FocusPolicy.NoFocus
        )
        self.show()
        self.raise_()
        if take_focus:
            self.setFocus()
        QApplication.instance().installEventFilter(self)

    def _fit(self) -> None:
        """Подгоняет размер и место списка под его варианты и поле."""
        box = self._box
        longest = max(
            (text_width(label, "body") for _, label in self._choices), default=0
        )
        self._inner_width = max(round(box.width()), longest + 2 * ITEM_PADDING_X)
        visible = min(len(self._choices), MAX_VISIBLE)
        self._inner_height = visible * ITEM_HEIGHT + 2 * LIST_PADDING
        total_width = self._inner_width + 2 * SHADOW_PAD
        total_height = self._inner_height + TOP_PAD + SHADOW_PAD
        anchor = self._anchor
        corner = anchor.mapTo(self._window, QPoint(round(box.left()), 0))
        bottom = anchor.mapTo(self._window, QPoint(0, round(box.bottom()))).y()
        top_of_field = anchor.mapTo(self._window, QPoint(0, round(box.top()))).y()
        x = corner.x() - SHADOW_PAD
        y = bottom
        if y + total_height > self._window.height() and top_of_field > total_height:
            y = top_of_field - total_height + SHADOW_PAD  # над полем
        self.setGeometry(x, y, total_width, total_height)

    def replace_options(
        self,
        options: Sequence[Option],
        selected: object,
        on_pick: Callable[[object], None],
        on_stage: Optional[Callable[[object], Optional[Stage]]] = None,
    ) -> None:
        """Меняет варианты в том же открытом списке (следующая ступень выбора).

        Args:
            options: Новые варианты (значение, подпись).
            selected: Значение, которое выделяется жирным.
            on_pick: Вызывается с выбранным значением.
            on_stage: Как в конструкторе: может вернуть ещё одну ступень.
        """
        self._choices = list(options)
        self._selected = selected
        self._on_pick = on_pick
        self._on_stage = on_stage
        self._hover = -1
        self._offset = 0
        self._fit()
        self.update()

    @property
    def options(self) -> List[Option]:
        """Варианты, которые показаны сейчас."""
        return list(self._choices)

    def sizeHint(self) -> QSize:
        return self.size()

    # --- рисование ---

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        begin(painter)
        shape = QRectF(SHADOW_PAD, TOP_PAD, self._inner_width, self._inner_height)
        draw_shadows(
            painter,
            shape,
            LIST_RADIUS,
            (Shadow(4, 12, pal.shadow, 0.14), Shadow(1, 3, pal.shadow, 0.06)),
        )
        fill_rounded(painter, shape, LIST_RADIUS, pal.card, pal.line)
        visible = min(len(self._choices), MAX_VISIBLE)
        for row in range(visible):
            index = self._offset + row
            value, text = self._choices[index]
            top = TOP_PAD + LIST_PADDING + row * ITEM_HEIGHT
            if index == self._hover:
                chip = QRectF(
                    SHADOW_PAD + LIST_PADDING,
                    top + 1,
                    self._inner_width - 2 * LIST_PADDING,
                    ITEM_HEIGHT - 2,
                )
                fill_rounded(painter, chip, 6, mix(pal.card, pal.primary_soft, 0.55))
            chosen = value == self._selected
            painter.setFont(font("body_strong" if chosen else "body"))
            painter.setPen(qcolor(pal.primary_ink if chosen else pal.ink))
            painter.drawText(
                QRectF(
                    SHADOW_PAD + ITEM_PADDING_X, top, self._inner_width, ITEM_HEIGHT
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

    # --- мышь и клавиатура ---

    def _index_at(self, y: float) -> int:
        row = int((y - TOP_PAD - LIST_PADDING) // ITEM_HEIGHT)
        index = self._offset + row
        if 0 <= row < MAX_VISIBLE and 0 <= index < len(self._choices):
            return index
        return -1

    def _inside(self, x: float, y: float) -> bool:
        return (
            SHADOW_PAD <= x <= SHADOW_PAD + self._inner_width
            and TOP_PAD <= y <= TOP_PAD + self._inner_height
        )

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        index = self._index_at(pos.y()) if self._inside(pos.x(), pos.y()) else -1
        if index != self._hover:
            self._hover = index
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        pos = event.position()
        if not self._inside(pos.x(), pos.y()):
            self.close_list()
            return
        index = self._index_at(pos.y())
        if index >= 0:
            value = self._choices[index][0]
            if self._on_stage is not None:
                stage = self._on_stage(value)
                if stage is not None:  # следующая ступень в том же списке
                    self.replace_options(*stage)
                    return
            self.close_list()
            self._on_pick(value)

    def wheelEvent(self, event) -> None:
        extra = len(self._choices) - MAX_VISIBLE
        if extra <= 0:
            return
        step = -1 if event.angleDelta().y() > 0 else 1
        self._offset = min(max(self._offset + step, 0), extra)
        self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_list()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Закрывает список при нажатии вне его и при изменении окна."""
        kind = event.type()
        if kind == QEvent.Type.MouseButtonPress:
            if not self._press_is_ours(event.globalPosition().toPoint()):
                self.close_list()
        elif kind == QEvent.Type.Resize and watched is self._window:
            self.close_list()
        elif kind in (QEvent.Type.WindowDeactivate, QEvent.Type.Hide):
            if watched is self._window:
                self.close_list()
        return False

    def _press_is_ours(self, point: QPoint) -> bool:
        """Нажатие по самому списку или по полю, которое его открыло.

        На поле нажатие не закрывает список: поле само решает, закрыть его или
        открыть заново.
        """
        for widget in (self, self._anchor):
            area = QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())
            if area.contains(point):
                return True
        return False

    def close_list(self) -> None:
        """Закрывает список."""
        if self._closed:
            return
        self._closed = True
        QApplication.instance().removeEventFilter(self)
        self.hide()
        self.deleteLater()
        if self._on_close is not None:
            self._on_close()
