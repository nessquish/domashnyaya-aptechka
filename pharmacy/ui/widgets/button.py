"""Кнопка из макета: обычная, главная и опасная, с иконкой и без."""

from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QWidget

from pharmacy.ui.fonts import font, line_height, text_width
from pharmacy.ui.icons import icon_pixmap
from pharmacy.ui.paint import (
    Shadow,
    backdrop,
    begin,
    draw_shadows,
    fill_rounded,
    qcolor,
)
from pharmacy.ui import theme
from pharmacy.ui.theme import SHADOW_PAD, mix, palette

ICON_GAP = 6
DISABLED_SHARE = 0.55  # насколько цвета неактивной кнопки уходят в фон
HOVER_SHARE = 0.07
PRESSED_SHARE = 0.14
VERTICAL_PADDING = 6  # минимальный отступ текста кнопки сверху и снизу


@dataclass(frozen=True)
class _Size:
    height: int
    padding: int
    font: str
    icon: int


SIZES = {
    "md": _Size(theme.CONTROL_HEIGHT, 16, "body_medium", 14),
    "sm": _Size(theme.CONTROL_HEIGHT_SMALL, 10, "small_medium", 13),
    "lg": _Size(theme.CONTROL_HEIGHT_LARGE, 16, "body_strong", 14),
}

VARIANTS = ("default", "primary", "danger", "danger_solid")


def _colors(variant: str) -> Tuple[str, str, str]:
    """Возвращает (заливка, граница, текст) кнопки в спокойном состоянии."""
    pal = palette()
    return {
        "default": (pal.input_bg, pal.line, pal.ink_2),
        "primary": (pal.primary, pal.primary, pal.on_primary),
        "danger": (pal.input_bg, pal.red_line, pal.red),
        "danger_solid": (pal.red, pal.red, pal.on_primary),
    }[variant]


def _shadows(variant: str) -> Tuple[Shadow, ...]:
    """Тени кнопки: у цветных кнопок тень того же цвета."""
    pal = palette()
    if variant == "primary":
        return (Shadow(3, 8, pal.primary, 0.28), Shadow(1, 2, pal.primary, 0.12))
    if variant == "danger_solid":
        return (Shadow(3, 8, pal.red, 0.28), Shadow(1, 2, pal.red, 0.12))
    return (Shadow(1, 3, pal.shadow, 0.08), Shadow(2, 6, pal.shadow, 0.05))


def button_height(size: str = "md") -> int:
    """Высота кнопки: по макету, но не меньше, чем нужно крупному тексту."""
    spec = SIZES[size]
    return max(spec.height, line_height(spec.font) + 2 * VERTICAL_PADDING)


def measure_button(text: str, size: str = "md", icon: Optional[str] = None) -> int:
    """Ширина кнопки по тексту и иконке (без полей под тень).

    Нужна, чтобы сделать кнопки в одном столбце одинаковой ширины: результат
    передаётся в параметр ``width`` кнопок.
    """
    spec = SIZES[size]
    width = text_width(text, spec.font)
    if icon:
        width += theme.scaled(spec.icon) + ICON_GAP
    return width + 2 * spec.padding


class Button(QAbstractButton):
    """Кнопка, нарисованная кодом.

    Меняет вид при наведении и нажатии, умеет быть неактивной и растягиваться
    на всю ширину, если ей позволяет размещение.
    """

    def __init__(
        self,
        text: str,
        command: Optional[Callable[[], None]] = None,
        variant: str = "default",
        size: str = "md",
        icon: Optional[str] = None,
        width: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Создаёт кнопку.

        Args:
            text: Подпись.
            command: Что вызвать при нажатии.
            variant: ``default``, ``primary``, ``danger`` или ``danger_solid``.
            size: ``md`` (32 px), ``sm`` (26 px) или ``lg`` (36 px).
            icon: Название иконки из ``icons.ICONS`` слева от подписи.
            width: Ширина кнопки в пикселях (по умолчанию по тексту).

        Raises:
            ValueError: Если такого вида кнопки нет.
        """
        super().__init__(parent)
        if variant not in VARIANTS:
            raise ValueError(f"Неизвестный вид кнопки: {variant}")
        self.setText(text)
        self._variant = variant
        self._size_name = size
        self._spec = SIZES[size]
        self._icon = icon
        self._height = button_height(size)
        self._body_width = width
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self._height + 2 * SHADOW_PAD)
        if command is not None:
            self.clicked.connect(lambda _checked=False: command())

    @property
    def enabled(self) -> bool:
        """Нажимается ли кнопка."""
        return self.isEnabled()

    def set_enabled(self, enabled: bool) -> None:
        """Включает или выключает кнопку."""
        self.setEnabled(enabled)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor
        )

    def set_text(self, text: str) -> None:
        """Меняет подпись."""
        self.setText(text)
        self.updateGeometry()
        self.update()

    def invoke(self) -> None:
        """Нажимает кнопку программно."""
        if self.isEnabled():
            self.click()

    def sizeHint(self) -> QSize:
        body = self._body_width or measure_button(
            self.text(), self._size_name, self._icon
        )
        return QSize(body + 2 * SHADOW_PAD, self._height + 2 * SHADOW_PAD)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _state_colors(self) -> Tuple[str, str, str]:
        """Цвета с учётом наведения, нажатия и недоступности."""
        fill, border, ink = _colors(self._variant)
        if not self.isEnabled():
            bg = backdrop(self)
            return tuple(mix(c, bg, DISABLED_SHARE) for c in (fill, border, ink))
        if self.isDown() or self.underMouse():
            share = PRESSED_SHARE if self.isDown() else HOVER_SHARE
            tint = (
                "#000000"
                if self._variant in ("primary", "danger_solid")
                else palette().primary
            )
            fill = mix(fill, tint, share)
        return fill, border, ink

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        begin(painter)
        fill, border, ink = self._state_colors()
        body = QRectF(
            SHADOW_PAD, SHADOW_PAD, self.width() - 2 * SHADOW_PAD, self._height
        )
        if self.isEnabled():
            draw_shadows(painter, body, theme.CONTROL_RADIUS, _shadows(self._variant))
        fill_rounded(painter, body, theme.CONTROL_RADIUS, fill, border)

        icon_size = theme.scaled(self._spec.icon)
        content = text_width(self.text(), self._spec.font)
        if self._icon:
            content += icon_size
            if self.text():
                content += ICON_GAP
        left = body.left() + (body.width() - content) / 2
        if self._icon:
            glyph = icon_pixmap(self._icon, icon_size, ink)
            if self.text():
                icon_x = left
                left += icon_size + ICON_GAP
            else:
                icon_x = body.center().x() - icon_size / 2
            painter.drawPixmap(
                round(icon_x), round(body.center().y() - icon_size / 2), glyph
            )

        painter.setPen(qcolor(ink))
        painter.setFont(font(self._spec.font))
        text_box = QRectF(left, body.top(), body.right() - left, body.height())
        painter.drawText(
            text_box,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.text(),
        )

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)
