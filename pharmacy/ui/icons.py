"""Иконки макета (линейный набор Lucide), нарисованные кодом.

Каждая иконка описана набором простых фигур в квадрате 24 на 24. Из них
собирается SVG нужного цвета и толщины, а Qt рисует его чётко в любом размере
и на экранах с любой плотностью пикселей. Файлов с картинками нет.
"""

from functools import lru_cache
from typing import Dict, Tuple, Union

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

GRID = 24  # размер квадрата, в котором описаны иконки

Path = Tuple[str, str]
Circle = Tuple[str, float, float, float]
Rect = Tuple[str, float, float, float, float, float]
Primitive = Union[Path, Circle, Rect]


def _path(data: str) -> Path:
    return ("path", data)


def _filled(data: str) -> Path:
    return ("fill", data)


def _circle(cx: float, cy: float, r: float) -> Circle:
    return ("circle", cx, cy, r)


def _rect(x: float, y: float, w: float, h: float, rx: float = 0) -> Rect:
    return ("rect", x, y, w, h, rx)


ICONS: Dict[str, Tuple[Primitive, ...]] = {
    "search": (_circle(11, 11, 8), _path("m21 21-4.3-4.3")),
    "calendar": (
        _rect(3, 4, 18, 18, 2),
        _path("M16 2v4M8 2v4M3 10h18"),
    ),
    "cart": (
        _circle(8, 21, 1),
        _circle(19, 21, 1),
        _path(
            "M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57"
            "l1.65-7.43H5.12"
        ),
    ),
    "clock": (_circle(12, 12, 10), _path("M12 6v6l4 2")),
    "alert": (_circle(12, 12, 10), _path("M12 8v4M12 16h.01")),
    "x": (_path("M18 6 6 18M6 6l12 12"),),
    "trending-down": (
        _path("m22 17-8.5-8.5-5 5L2 7"),
        _path("M16 17h6v-6"),
    ),
    "pencil": (
        _path(
            "M21.17 6.81a1 1 0 0 0-3.98-3.98L3.84 16.17a2 2 0 0 0-.5.83l-1.32"
            " 4.35a.5.5 0 0 0 .62.62l4.35-1.32a2 2 0 0 0 .83-.5z"
        ),
    ),
    "plus": (_path("M5 12h14M12 5v14"),),
    "check": (_path("M20 6 9 17l-5-5"),),
    "logout": (
        _path("M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"),
        _path("m16 17 5-5-5-5M21 12H9"),
    ),
    "arrow-left": (_path("m12 19-7-7 7-7M19 12H5"),),
    "arrow-right": (_path("M5 12h14m-7-7 7 7-7 7"),),
    "arrow-down": (_path("M12 5v14m7-7-7 7-7-7"),),
    "arrow-up": (_path("m5 12 7-7 7 7M12 19V5"),),
    "chevron-left": (_path("m15 18-6-6 6-6"),),
    "chevron-right": (_path("m9 18 6-6-6-6"),),
    "chevron-down": (_path("m6 9 6 6 6-6"),),
    "panel-left": (_rect(3, 3, 18, 18, 2), _path("M9 3v18")),
    "moon": (_path("M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9z"),),
    "sun": (
        _circle(12, 12, 4),
        _path(
            "M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41"
            "M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"
        ),
    ),
    "square": (_rect(5, 5, 14, 14, 1.5),),
    "home": (
        _path("m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"),
        _path("M9 22V12h6v10"),
    ),
    "box": (
        _path(
            "M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0"
            " 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"
        ),
        _path("m3.3 7 8.7 5 8.7-5M12 22V12"),
    ),
    "bell": (
        _path("M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"),
        _path("M10.3 21a1.94 1.94 0 0 0 3.4 0"),
    ),
    "sliders": (
        _path("M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"),
        _path("M1 14h6M9 8h6M17 16h6"),
    ),
    "user": (
        _path("M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"),
        _circle(12, 7, 4),
    ),
    "database": (
        _path("M21 5c0 1.66-4.03 3-9 3S3 6.66 3 5s4.03-3 9-3 9 1.34 9 3z"),
        _path("M3 5v14a9 3 0 0 0 18 0V5M3 12a9 3 0 0 0 18 0"),
    ),
    "info": (_circle(12, 12, 10), _path("M12 16v-4M12 8h.01")),
    "minus": (_path("M5 12h14"),),
    "cross": (_filled("M9 2h6v7h7v6h-7v7H9v-7H2V9h7z"),),
    "eye": (
        _path(
            "M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7"
            " 10.75 10.75 0 0 1-19.88 0"
        ),
        _circle(12, 12, 3),
    ),
    "eye-off": (
        _path(
            "M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696"
            " 10.747 10.747 0 0 1-1.444 2.49"
        ),
        _path("M14.084 14.158a3 3 0 0 1-4.242-4.242"),
        _path(
            "M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696"
            " 10.75 10.75 0 0 1 4.446-5.143"
        ),
        _path("m2 2 20 20"),
    ),
}


def _primitive_svg(primitive: Primitive, color: str) -> str:
    """Переводит одну фигуру в тег SVG."""
    kind = primitive[0]
    if kind == "path":
        return f'<path d="{primitive[1]}"/>'
    if kind == "fill":
        return f'<path d="{primitive[1]}" fill="{color}" stroke="none"/>'
    if kind == "circle":
        _, cx, cy, radius = primitive
        return f'<circle cx="{cx}" cy="{cy}" r="{radius}"/>'
    _, x, y, width, height, corner = primitive
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{corner}"/>'


def icon_svg(name: str, color: str, stroke_width: float = 2.0) -> str:
    """Собирает SVG иконки.

    Raises:
        KeyError: Если такой иконки нет.
    """
    body = "".join(_primitive_svg(p, color) for p in ICONS[name])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {GRID} {GRID}" '
        f'fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )


@lru_cache(maxsize=512)
def _render(
    name: str, size: int, color: str, stroke_width: float, ratio: float
) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(icon_svg(name, color, stroke_width).encode()))
    pixmap = QPixmap(round(size * ratio), round(size * ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(ratio)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def icon_pixmap(name: str, size: int, color: str, stroke_width: float = 2.0) -> QPixmap:
    """Рисует иконку.

    Args:
        name: Название иконки из ``ICONS``.
        size: Сторона квадрата в логических пикселях.
        color: Цвет ``#RRGGBB``.
        stroke_width: Толщина линии в единицах сетки 24 на 24.

    Raises:
        KeyError: Если такой иконки нет.
    """
    screen = QGuiApplication.primaryScreen()
    ratio = screen.devicePixelRatio() if screen is not None else 1.0
    return _render(name, size, color, stroke_width, ratio)
