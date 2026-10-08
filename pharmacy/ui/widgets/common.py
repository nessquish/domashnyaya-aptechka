"""Общие мелочи для виджетов: подписи, цвета по ролям, нажимаемые виджеты."""

from typing import Callable, Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPalette
from PySide6.QtWidgets import QLabel, QLayout, QSizePolicy, QWidget

from pharmacy.ui.fonts import font, line_height
from pharmacy.ui.theme import palette


def role_color(role: str) -> str:
    """Цвет по роли палитры (``ink``, ``primary`` ...) или сам цвет ``#RRGGBB``."""
    return role if role.startswith("#") else getattr(palette(), role)


LABEL_BORDER = 2  # у подписи прежнего интерфейса была рамка в 2 пикселя
LABEL_PAD = 1  # и вертикальный отступ в 1 пиксель, если его не обнулили


class ElidedLabel(QLabel):
    """Однострочная подпись: если места мало, текст обрезается многоточием.

    Подпись может сжиматься уже своего текста, поэтому длинные названия не
    растягивают окно и оно спокойно уменьшается (например, до половины экрана).
    """

    MIN_WIDTH = 36

    def minimumSizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(min(hint.width(), self.MIN_WIDTH), hint.height())

    def paintEvent(self, event) -> None:
        area = self.contentsRect()
        metrics = self.fontMetrics()
        full = metrics.horizontalAdvance(self.text())
        if full <= area.width() or self.wordWrap():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setFont(self.font())
        painter.setPen(self.palette().color(QPalette.ColorRole.WindowText))
        shown = metrics.elidedText(
            self.text(), Qt.TextElideMode.ElideRight, area.width()
        )
        painter.drawText(area, int(self.alignment()), shown)


def pad(
    widget: QLabel, left: int = 0, top: int = 0, right: int = 0, bottom: int = 0
) -> None:
    """Задаёт внешние отступы подписи поверх её собственных (рамка и отступ).

    Интервалы между подписями в макете отсчитываются от краёв рамки подписи, а
    не от самого текста, поэтому собственные отступы нужно сохранять.
    """
    inner = widget.property("inner_pad")
    side = widget.property("side_pad")
    widget.setContentsMargins(left + side, top + inner, right + side, bottom + inner)
    line = widget.property("line_height")
    if line:  # однострочная подпись: высота как в макете
        widget.setFixedHeight(line + top + bottom + 2 * inner)


def label(
    text: str = "",
    style: str = "body",
    color: str = "ink",
    parent: Optional[QWidget] = None,
    wrap: bool = False,
    strike: bool = False,
    tight: bool = False,
    bare: bool = False,
) -> QLabel:
    """Создаёт подпись: текст в стиле макета нужного цвета.

    У подписи те же собственные отступы, что и в макете: рамка 2 пикселя и
    вертикальный отступ 1 пиксель (у «тесных» подписей отступа нет).

    Args:
        text: Текст.
        style: Стиль из ``theme.TYPOGRAPHY``.
        color: Роль цвета палитры или ``#RRGGBB``.
        parent: Родитель.
        wrap: Переносить длинный текст на следующие строки.
        strike: Зачеркнуть текст.
        tight: Без вертикального отступа (только рамка).
        bare: Совсем без отступов (текст, который в макете нарисован прямо на
            полотне, например в шапке таблицы).
    """
    result = QLabel(text, parent) if wrap else ElidedLabel(text, parent)
    result.setProperty("line_height", 0 if wrap else line_height(style))
    result.setProperty("side_pad", 0 if bare else LABEL_BORDER)
    result.setProperty(
        "inner_pad", 0 if bare else LABEL_BORDER + (0 if tight else LABEL_PAD)
    )
    pad(result)
    result.setFont(font(style))
    if strike:
        struck = result.font()
        struck.setStrikeOut(True)
        result.setFont(struck)
    recolor(result, color)
    result.setWordWrap(wrap)
    result.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    result.setMargin(0)
    result.setIndent(0)
    return result


def recolor(widget: QWidget, color: str) -> None:
    """Задаёт цвет текста виджета."""
    colors = widget.palette()
    colors.setColor(QPalette.ColorRole.WindowText, QColor(role_color(color)))
    colors.setColor(QPalette.ColorRole.Text, QColor(role_color(color)))
    widget.setPalette(colors)


def clickable(widget: QWidget, command: Callable[[], None]) -> None:
    """Делает виджет нажимаемым: рука при наведении и вызов команды по клику."""
    widget.setCursor(Qt.CursorShape.PointingHandCursor)

    def press(event: QMouseEvent) -> None:
        event.accept()  # без этого нажатие уходит родителю, а отпускание теряется

    def release(event: QMouseEvent) -> None:
        inside = QRect(0, 0, widget.width(), widget.height()).contains(
            event.position().toPoint()
        )
        if event.button() == Qt.MouseButton.LeftButton and inside:
            command()

    widget.mousePressEvent = press  # type: ignore[method-assign]
    widget.mouseReleaseEvent = release  # type: ignore[method-assign]


class Line(QWidget):
    """Тонкая горизонтальная линия-разделитель."""

    def __init__(self, color: str = "line_soft", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._color = color
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event) -> None:
        QPainter(self).fillRect(self.rect(), QColor(role_color(self._color)))


def clear_layout(layout: QLayout) -> None:
    """Удаляет всё, что лежит в раскладке (виджеты и вложенные раскладки)."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def fixed_height(widget: QWidget, height: int) -> None:
    """Фиксирует высоту виджета, ширину оставляет гибкой."""
    widget.setFixedHeight(height)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
