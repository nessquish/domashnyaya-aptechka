"""Раскладка из двух частей, которая переносит правую часть на вторую строку."""

from typing import List, Optional

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget


class TwoSideLayout(QLayout):
    """Левая и правая части в одну строку; в узком окне правая уходит под левую.

    Первым кладётся левый виджет, вторым правый. Пока обе части помещаются,
    они стоят в одной строке: левая слева, правая прижата к правому краю (или
    занимает всё остальное место, если ``align_right`` выключен). Если не
    помещаются, правая часть переходит на вторую строку. Высота при этом
    считается по ширине (``heightForWidth``), поэтому раскладка работает и в
    прокручиваемой области.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        align_right: bool = True,
        gap: int = 8,
        row_gap: int = 8,
    ) -> None:
        """Создаёт раскладку.

        Args:
            parent: Виджет, на который она ставится.
            align_right: Прижимать правую часть к правому краю.
            gap: Расстояние между частями в одной строке.
            row_gap: Расстояние между строками, когда правая часть перенесена.
        """
        super().__init__(parent)
        self._items: List[QLayoutItem] = []
        self._align_right = align_right
        self._gap = gap
        self._row_gap = row_gap

    # --- содержимое ---

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> Optional[QLayoutItem]:
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation.Horizontal

    # --- размеры ---

    def _hints(self):
        sizes = [item.sizeHint() for item in self._items[:2]]
        while len(sizes) < 2:
            sizes.append(QSize(0, 0))
        return sizes

    def _is_wrapped(self, inner_width: int) -> bool:
        left, right = self._hints()
        if not right.width() or not left.width():
            return False
        return left.width() + self._gap + right.width() > inner_width

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        margins = self.contentsMargins()
        inner = width - margins.left() - margins.right()
        left, right = self._hints()
        if self._is_wrapped(inner):
            height = left.height() + self._row_gap + right.height()
        else:
            height = max(left.height(), right.height())
        return height + margins.top() + margins.bottom()

    def sizeHint(self) -> QSize:
        left, right = self._hints()
        margins = self.contentsMargins()
        gap = self._gap if left.width() and right.width() else 0
        return QSize(
            left.width() + gap + right.width() + margins.left() + margins.right(),
            max(left.height(), right.height()) + margins.top() + margins.bottom(),
        )

    def minimumSize(self) -> QSize:
        margins = self.contentsMargins()
        sizes = [item.minimumSize() for item in self._items[:2]]
        width = max((s.width() for s in sizes), default=0)
        height = max((s.height() for s in sizes), default=0)
        return QSize(
            width + margins.left() + margins.right(),
            height + margins.top() + margins.bottom(),
        )

    # --- расстановка ---

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        if not self._items:
            return
        margins = self.contentsMargins()
        x0 = rect.x() + margins.left()
        y0 = rect.y() + margins.top()
        width = rect.width() - margins.left() - margins.right()
        left, right = self._hints()
        left_item = self._items[0]
        right_item = self._items[1] if len(self._items) > 1 else None
        if right_item is None:
            left_item.setGeometry(QRect(x0, y0, width, left.height()))
            return
        if self._is_wrapped(width):
            left_item.setGeometry(
                QRect(x0, y0, min(left.width(), width), left.height())
            )
            y1 = y0 + left.height() + self._row_gap
            right_width = min(right.width(), width) if self._align_right else width
            x1 = x0 + width - right_width if self._align_right else x0
            right_item.setGeometry(QRect(x1, y1, right_width, right.height()))
            return
        row = max(left.height(), right.height())
        left_y = y0 + (row - left.height()) // 2
        right_y = y0 + (row - right.height()) // 2
        left_item.setGeometry(
            QRect(QPoint(x0, left_y), QSize(left.width(), left.height()))
        )
        if self._align_right:
            right_x, right_width = x0 + width - right.width(), right.width()
        else:
            right_x = x0 + left.width() + self._gap
            right_width = width - left.width() - self._gap
        right_item.setGeometry(QRect(right_x, right_y, right_width, right.height()))
