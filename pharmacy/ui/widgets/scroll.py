"""Прокручиваемая область со своей тонкой полосой прокрутки."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from pharmacy.ui.theme import mix, palette

TRACK_WIDTH = 10
THUMB_WIDTH = 6
THUMB_MARGIN = 4  # отступ ползунка от правого края окна
MIN_THUMB = 28
WHEEL_STEP = 14  # колёсико двигает на три таких шага


class ScrollArea(QScrollArea):
    """Область, в которой содержимое прокручивается, если оно выше окна.

    Содержимое добавляется в ``body``. Полоса прокрутки тонкая, ползунок виден
    только при переполнении. Поле под полосу занято всегда, поэтому ширина
    содержимого не прыгает.

    Attributes:
        body: Вертикальная раскладка для содержимого.
    """

    def __init__(
        self, gutter: int = TRACK_WIDTH, parent: Optional[QWidget] = None
    ) -> None:
        """Создаёт область.

        Args:
            gutter: Ширина поля справа, в котором рисуется ползунок.
            parent: Родитель.
        """
        super().__init__(parent)
        pal = palette()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        # Полоса снизу нужна только в узком окне, когда открыто боковое меню.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        thumb = mix(pal.line, pal.ink_3, 0.55)
        self.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget {"
            " background: transparent; }"
            "QScrollBar:vertical {"
            f" background: transparent; width: {gutter}px; margin: 0; }}"
            "QScrollBar::handle:vertical {"
            f" background: {thumb}; border-radius: {THUMB_WIDTH // 2}px;"
            f" min-height: {MIN_THUMB}px;"
            f" margin: 0 {THUMB_MARGIN}px 0 {gutter - THUMB_WIDTH - THUMB_MARGIN}px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
            " height: 0; }"
            "QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {"
            " background: transparent; }"
            "QAbstractScrollArea::corner { background: transparent; }"
            "QScrollBar:horizontal {"
            f" background: transparent; height: {THUMB_WIDTH + 2 * THUMB_MARGIN}px;"
            " margin: 0; }"
            "QScrollBar::handle:horizontal {"
            f" background: {thumb}; border-radius: {THUMB_WIDTH // 2}px;"
            f" min-width: {MIN_THUMB}px; margin: {THUMB_MARGIN}px 0; }}"
            "QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {"
            " width: 0; }"
            "QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {"
            " background: transparent; }"
        )
        self.verticalScrollBar().setSingleStep(WHEEL_STEP)
        host = QWidget()
        host.setObjectName("scroll-body")
        self.body = QVBoxLayout(host)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        self.setWidget(host)
        self.viewport().setAutoFillBackground(False)

    def scroll_to_top(self) -> None:
        """Возвращает содержимое в начало (при смене экрана)."""
        self.verticalScrollBar().setValue(0)
