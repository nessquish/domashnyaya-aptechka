"""Строка со скруглённой цветной подложкой (непрочитанное уведомление)."""

from typing import Optional

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QVBoxLayout, QWidget

from pharmacy.ui.paint import begin, fill_rounded

RADIUS = 6
MARGIN_X = 4  # отступ подложки от краёв строки
MARGIN_Y = 2
INSET = 2  # отступ содержимого от края подложки: оно не закрывает её скругления


class Highlight(QWidget):
    """Рамка с подложкой цвета ``color`` и скруглёнными углами.

    Содержимое добавляется в ``body``. Подложка отступает от краёв строки, а
    содержимое от подложки, поэтому прямоугольники виджетов не торчат из углов.

    Attributes:
        body: Раскладка для содержимого строки.
        padding_x: Полный горизонтальный отступ содержимого от края рамки.
        padding_y: Полный вертикальный отступ содержимого от края рамки.
    """

    padding_x = MARGIN_X + INSET
    padding_y = MARGIN_Y + INSET

    def __init__(self, color: str, parent: Optional[QWidget] = None) -> None:
        """Создаёт строку.

        Args:
            color: Цвет подложки ``#RRGGBB``.
        """
        super().__init__(parent)
        self._color = color
        self.backdrop_color = color
        self.body = QVBoxLayout(self)
        x, y = self.padding_x, self.padding_y
        self.body.setContentsMargins(x, y, x, y)
        self.body.setSpacing(0)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        begin(painter)
        box = QRectF(
            MARGIN_X,
            MARGIN_Y,
            self.width() - 2 * MARGIN_X,
            self.height() - 2 * MARGIN_Y,
        )
        fill_rounded(painter, box, RADIUS, self._color)
