"""Общие приёмы рисования: цвета, скруглённые фигуры и мягкие тени."""

from dataclasses import dataclass
from statistics import NormalDist
from typing import Iterable, Optional, Tuple

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from pharmacy.ui.theme import palette

SHADOW_LAYERS = 14
# Границы слоёв тени: квантили нормального распределения, поэтому суммарная
# густота тени падает к краю так же плавно, как после гауссова размытия.
_QUANTILES = tuple(
    NormalDist().inv_cdf(1 - (index + 0.5) / SHADOW_LAYERS)
    for index in range(SHADOW_LAYERS)
)


def qcolor(color: str, opacity: float = 1.0) -> QColor:
    """Цвет ``#RRGGBB`` с прозрачностью от 0 до 1."""
    result = QColor(color)
    result.setAlphaF(opacity)
    return result


def backdrop(widget: QWidget) -> str:
    """Цвет, на котором лежит виджет (нужен, чтобы выключенные виджеты бледнели).

    Фон задают те родители, у которых есть поле ``backdrop_color``.
    """
    parent = widget.parentWidget()
    while parent is not None:
        color = getattr(parent, "backdrop_color", None)
        if color:
            return color
        parent = parent.parentWidget()
    return palette().bg


def begin(painter: QPainter) -> None:
    """Включает сглаживание линий и текста."""
    painter.setRenderHints(
        QPainter.RenderHint.Antialiasing
        | QPainter.RenderHint.TextAntialiasing
        | QPainter.RenderHint.SmoothPixmapTransform
    )


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


@dataclass(frozen=True)
class Shadow:
    """Тень под фигурой (аналог ``box-shadow`` из макета).

    Attributes:
        dy: Сдвиг вниз.
        blur: Размытие.
        color: Цвет ``#RRGGBB``.
        opacity: Непрозрачность в самой густой части, от 0 до 1.
    """

    dy: float
    blur: float
    color: str
    opacity: float


def draw_shadows(
    painter: QPainter, rect: QRectF, radius: float, shadows: Iterable[Shadow]
) -> None:
    """Рисует тени под скруглённым прямоугольником одну за другой."""
    for shadow in shadows:
        _draw_shadow(painter, rect, radius, shadow)


def _draw_shadow(
    painter: QPainter, rect: QRectF, radius: float, shadow: Shadow
) -> None:
    """Рисует одну мягкую тень.

    Тень собирается из нескольких слоёв с растущим размером: края получаются
    плавными, как у размытия, но без дорогого расчёта.
    """
    sigma = shadow.blur / 2  # как в CSS: размытие в 2 раза шире σ гауссианы
    layer_opacity = 1 - (1 - shadow.opacity) ** (1 / SHADOW_LAYERS)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(qcolor(shadow.color, layer_opacity))
    shifted = rect.translated(0, shadow.dy)
    for quantile in _QUANTILES:
        grow = sigma * quantile
        box = shifted.adjusted(-grow, -grow, grow, grow)
        if box.width() <= 0 or box.height() <= 0:
            continue
        painter.drawRoundedRect(box, max(radius + grow, 0), max(radius + grow, 0))


def fill_rounded(
    painter: QPainter,
    rect: QRectF,
    radius: float,
    fill: Optional[str],
    border: Optional[str] = None,
    border_width: float = 1.0,
) -> None:
    """Рисует скруглённый прямоугольник с заливкой и рамкой внутри границы."""
    half = border_width / 2 if border else 0
    box = rect.adjusted(half, half, -half, -half)
    painter.setBrush(qcolor(fill) if fill else Qt.BrushStyle.NoBrush)
    if border:
        pen = QPen(qcolor(border))
        pen.setWidthF(border_width)
        painter.setPen(pen)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(box, radius - half, radius - half)


def padding(widget: QWidget) -> Tuple[int, int, int, int]:
    """Поля содержимого виджета (слева, сверху, справа, снизу)."""
    margins = widget.contentsMargins()
    return margins.left(), margins.top(), margins.right(), margins.bottom()
