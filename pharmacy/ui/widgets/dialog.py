"""Модальные окна поверх затемнённого окна приложения."""

from typing import Callable, Optional

from PySide6.QtCore import QEvent, QObject, QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from pharmacy.ui.icons import icon_pixmap
from pharmacy.ui.paint import begin, fill_rounded, qcolor
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.common import label
from pharmacy.ui import theme
from pharmacy.ui.theme import palette

SCRIM_OPACITY = 0.42
PADDING = 24
WARN_SIZE = 42


class Modal(QWidget):
    """Белое окно по центру на затемнённом фоне, в которое кладётся содержимое.

    Это обычный виджет поверх всего окна приложения (а не отдельное окно).
    Закрывается по Esc. Пока окно открыто, остальной интерфейс закрыт
    затемнением и не реагирует на нажатия. Содержимое добавляется в ``body``.

    Attributes:
        body: Раскладка для содержимого окна (внутри отступов).
        width_px: Ширина окна.
    """

    def __init__(
        self,
        host: QWidget,
        width: int = 400,
        on_enter: Optional[Callable[[], None]] = None,
    ) -> None:
        """Открывает пустое окно.

        Args:
            host: Окно или экран, поверх которого открывается диалог.
            width: Ширина окна.
            on_enter: Что вызвать по клавише Enter (необязательно).
        """
        self._window = host.window()
        super().__init__(self._window)
        self._on_enter = on_enter
        self.width_px = width
        self._closed = False
        self.setGeometry(self._window.rect())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.card = Card(radius=theme.MODAL_RADIUS, elevated=True)
        outer.addWidget(self.card, 0, Qt.AlignmentFlag.AlignCenter)
        host_widget = QWidget()
        self.card.body.addWidget(host_widget)
        self.body = QVBoxLayout(host_widget)
        self.body.setContentsMargins(PADDING, PADDING, PADDING, PADDING)
        self.body.setSpacing(0)
        self.card.setFixedWidth(
            width + 2 * (theme.MODAL_SHADOW_PAD + self.card.inner_inset)
        )
        self.show()
        self.raise_()
        self.setFocus()
        self._window.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Растягивает затемнение вместе с окном."""
        if watched is self._window and event.type() == QEvent.Type.Resize:
            self.setGeometry(self._window.rect())
        return False

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), qcolor(palette().overlay, SCRIM_OPACITY))

    def mousePressEvent(self, event) -> None:
        event.accept()  # затемнение не пропускает нажатия к тому, что под ним

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_modal()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._on_enter is not None:
                self._on_enter()
        else:
            super().keyPressEvent(event)

    def add_title(self, title: str) -> None:
        """Добавляет заголовок."""
        self.body.addWidget(label(title, "modal_title"))
        self.body.addSpacing(8)

    def add_text(self, message: str, bottom: int = 0) -> None:
        """Добавляет пояснение под заголовком."""
        self.body.addWidget(label(message, "body", "ink_2", wrap=True))
        if bottom:
            self.body.addSpacing(bottom)

    def footer(self) -> QHBoxLayout:
        """Создаёт ряд для кнопок справа внизу окна."""
        self.body.addSpacing(16)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addStretch(1)
        self.body.addLayout(row)
        return row

    @property
    def is_open(self) -> bool:
        """Открыто ли окно."""
        return not self._closed

    def close_modal(self) -> None:
        """Закрывает окно и снимает затемнение."""
        if self._closed:
            return
        self._closed = True
        self._window.removeEventFilter(self)
        self.hide()
        self.deleteLater()


class _Warning(QWidget):
    """Красный круг с восклицательным знаком над заголовком."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(WARN_SIZE, WARN_SIZE)

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        begin(painter)
        fill_rounded(
            painter, QRectF(0, 0, WARN_SIZE, WARN_SIZE), WARN_SIZE / 2, pal.red_bg
        )
        painter.drawPixmap(
            (WARN_SIZE - 20) // 2,
            (WARN_SIZE - 20) // 2,
            icon_pixmap("alert", 20, pal.red),
        )


class Dialog(Modal):
    """Окно с заголовком, текстом и кнопками «Отмена» и подтверждения.

    Закрывается по «Отмена», по подтверждению и по клавише Esc. Enter
    подтверждает действие.
    """

    def __init__(
        self,
        host: QWidget,
        title: str,
        message: str,
        confirm_text: str,
        on_confirm: Callable[[], None],
        confirm_variant: str = "primary",
        cancel_text: str = "Отмена",
        warning: bool = False,
        width: int = 400,
        info: bool = False,
    ) -> None:
        """Показывает окно.

        Args:
            host: Окно или экран, поверх которого открывается диалог.
            title: Заголовок.
            message: Пояснение.
            confirm_text: Подпись кнопки подтверждения.
            on_confirm: Что сделать после подтверждения (окно закроется само).
            confirm_variant: Вид кнопки подтверждения (``primary``, ``danger_solid``).
            cancel_text: Подпись кнопки отмены.
            warning: Показать красный значок восклицания над заголовком.
            width: Ширина окна.
            info: Только сообщение: одна кнопка, без «Отмена».
        """
        super().__init__(host, width, on_enter=self._confirm)
        self._on_confirm = on_confirm
        if warning:
            self.body.addWidget(_Warning())
            self.body.addSpacing(14)
        self.add_title(title)
        self.add_text(message)
        buttons = self.footer()
        self.cancel_button = Button(cancel_text, self.close_modal)
        self.confirm_button = Button(
            confirm_text, self._confirm, variant=confirm_variant
        )
        if not info:
            buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.confirm_button)

    def _confirm(self) -> None:
        self.close_modal()
        self._on_confirm()
