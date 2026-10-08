"""Панель действий над выбранными строками таблицы («Выбрано: 2» и кнопки)."""

from typing import Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QWidget

from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.common import label
from pharmacy.ui.theme import palette

HEIGHT = 46
PADDING_X = 14


class ActionBar(QWidget):
    """Полоса цвета выделения с текстом слева и кнопками справа.

    Саму полосу вместе с гладкими верхними углами красит карточка, в которую
    вставлена панель.

    Attributes:
        buttons: Раскладка справа, в которую кладутся кнопки.
    """

    def __init__(self, card: Card, parent: Optional[QWidget] = None) -> None:
        """Создаёт скрытую панель.

        Args:
            card: Карточка, в которую вставлена панель.
        """
        super().__init__(parent)
        self._card = card
        self.backdrop_color = palette().bulk_bg
        self.setFixedHeight(HEIGHT)
        row = QHBoxLayout(self)
        row.setContentsMargins(PADDING_X, 0, PADDING_X, 0)
        row.setSpacing(0)
        self._text = label("", "small", "primary_ink", bare=True)
        row.addWidget(self._text)
        row.addStretch(1)
        self.buttons = QHBoxLayout()
        self.buttons.setContentsMargins(0, 0, 0, 0)
        self.buttons.setSpacing(4)
        row.addLayout(self.buttons)
        self.setVisible(False)

    @property
    def text(self) -> str:
        """Текст слева."""
        return self._text.text()

    def set_text(self, text: str) -> None:
        """Меняет текст слева."""
        self._text.setText(text)

    def show_bar(self, text: str) -> None:
        """Показывает панель у верхнего края карточки с текстом слева."""
        self._text.setText(text)
        self._card.set_band(HEIGHT, palette().bulk_bg)
        self.setVisible(True)

    def flash(self, text: str, on_done, ms: int = 2500) -> None:
        """Показывает короткое сообщение вместо кнопок и потом вызывает ``on_done``."""
        self.show_bar(text)
        for index in range(self.buttons.count()):
            widget = self.buttons.itemAt(index).widget()
            if widget is not None:
                widget.setVisible(False)
        QTimer.singleShot(ms, lambda: self._unflash(on_done))

    def _unflash(self, on_done) -> None:
        try:
            for index in range(self.buttons.count()):
                widget = self.buttons.itemAt(index).widget()
                if widget is not None:
                    widget.setVisible(True)
            on_done()
        except RuntimeError:  # экран уже закрыт
            pass

    def hide_bar(self) -> None:
        """Прячет панель (полосу карточки возвращает тот, кто её занимал раньше)."""
        self.setVisible(False)
