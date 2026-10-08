"""Поля из макета: подпись, рамка, подсказка и сообщение об ошибке.

``LabeledBox`` рисует рамку с подписью и ошибкой, а ``TextField`` добавляет
к ней ввод текста. Выпадающий список (``select.Select``) строится на той же
основе, поэтому выглядит так же.
"""

from typing import Callable, Optional, Tuple

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication, QKeySequence, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pharmacy.ui.fonts import font
from pharmacy.ui.icons import icon_pixmap
from pharmacy.ui.paint import Shadow, begin, draw_shadows, fill_rounded
from pharmacy.ui.widgets.common import clickable, label, pad, recolor
from pharmacy.ui import theme
from pharmacy.ui.theme import SHADOW_PAD, palette

RING_PAD = SHADOW_PAD  # поле вокруг рамки: помещается кольцо ошибки и тень
RING_WIDTH = 3  # толщина красного кольца вокруг поля с ошибкой
TEXT_INSET = 10
ICON_SIZE = 16
ICON_INSET = 10
MASK_CHAR = "•"
AREA_HEIGHT = 54  # высота многострочного поля
AREA_PADDING_TOP = 9


class _Frame(QWidget):
    """Нарисованная рамка поля: границу, кольцо ошибки и тень рисует владелец."""

    def __init__(self, owner: "LabeledBox", height: int) -> None:
        super().__init__(owner)
        self._owner = owner
        self._box_height = height
        self.setFixedHeight(height + 2 * RING_PAD)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        begin(painter)
        border, ring = self._owner.frame_colors()
        box = QRectF(RING_PAD, RING_PAD, self.width() - 2 * RING_PAD, self._box_height)
        draw_shadows(
            painter, box, theme.CONTROL_RADIUS, (Shadow(1, 2, pal.shadow, 0.05),)
        )
        if ring is not None:
            spread = RING_WIDTH
            fill_rounded(
                painter,
                box.adjusted(-spread, -spread, spread, spread),
                theme.CONTROL_RADIUS + spread,
                ring,
            )
        fill_rounded(painter, box, theme.CONTROL_RADIUS, pal.input_bg, border)
        self._owner.paint_content(painter, box)

    def box_rect(self) -> QRectF:
        """Видимая рамка поля внутри виджета (без полей под тень)."""
        return QRectF(RING_PAD, RING_PAD, self.width() - 2 * RING_PAD, self._box_height)

    def mousePressEvent(self, event) -> None:
        self._owner.frame_pressed(event)


class LabeledBox(QWidget):
    """Рамка поля с подписью сверху и сообщением об ошибке снизу.

    Рисует рамку (обычную, в фокусе или с ошибкой). Что лежит внутри рамки,
    решают наследники: они кладут виджеты в ``content`` или рисуют сами
    в ``paint_content``.

    Attributes:
        content: Горизонтальная раскладка внутри рамки.
    """

    def __init__(
        self,
        label_text: Optional[str] = None,
        required: bool = False,
        height: int = theme.CONTROL_HEIGHT,
        compact: bool = False,
        width: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Создаёт рамку.

        Args:
            label_text: Подпись над полем (None, если подписи нет).
            required: Добавить красную звёздочку к подписи.
            height: Высота рамки без полей под тень.
            compact: Вид фильтра на панели: граница цвета карточек.
            width: Ширина рамки. Если не задана, поле занимает всю ширину,
                которую даёт родитель.
            parent: Родитель.
        """
        super().__init__(parent)
        pal = palette()
        self._border = pal.line if compact else pal.input_line
        self._focused = False
        self._error: Optional[str] = None
        self._title: Optional[QLabel] = None
        self._box_height = height
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        if label_text is not None:
            outer.addWidget(self._build_label(label_text, required))
        self._frame = _Frame(self, height)
        outer.addWidget(self._frame)
        self.content = QHBoxLayout(self._frame)
        self.content.setContentsMargins(
            RING_PAD + TEXT_INSET, RING_PAD, RING_PAD + TEXT_INSET, RING_PAD
        )
        self.content.setSpacing(8)
        self._error_label = label("", "caption", "red", wrap=True)
        pad(self._error_label, RING_PAD, 4 - RING_PAD, RING_PAD, 0)
        self._error_label.setVisible(False)
        outer.addWidget(self._error_label)
        if width is not None:
            self.set_width(width)

    def _build_label(self, text: str, required: bool) -> QWidget:
        """Строит строку подписи над полем."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(RING_PAD, 0, RING_PAD, 5 - RING_PAD)
        layout.setSpacing(0)
        self._title = label(text, "label", "ink_2")
        layout.addWidget(self._title)
        if required:
            layout.addWidget(label(" *", "label", "red"))
        layout.addStretch(1)
        return row

    @property
    def title(self) -> str:
        """Подпись над полем (пустая, если подписи нет)."""
        return self._title.text() if self._title is not None else ""

    def set_title(self, text: str) -> None:
        """Меняет подпись над полем (например, добавляет единицу измерения)."""
        if self._title is not None:
            self._title.setText(text)

    def set_width(self, width: int) -> None:
        """Фиксирует ширину рамки (без полей под тень)."""
        self.setFixedWidth(width + 2 * RING_PAD)

    # --- ошибка ---

    @property
    def error(self) -> Optional[str]:
        """Текст ошибки или None."""
        return self._error

    def set_error(self, message: str = "") -> None:
        """Подсвечивает поле красным и показывает сообщение под ним.

        Args:
            message: Текст ошибки. Если пустой, поле только краснеет
                (сообщение показано в другом месте, например над формой).
        """
        self._error = message
        self._error_label.setText(message)
        self._error_label.setVisible(bool(message))
        self._frame.update()

    def clear_error(self) -> None:
        """Убирает подсветку ошибки."""
        if self._error is None:
            return
        self._error = None
        self._error_label.setVisible(False)
        self._frame.update()

    # --- рисование ---

    def frame_colors(self) -> Tuple[str, Optional[str]]:
        """Цвет границы и кольца для текущего состояния."""
        pal = palette()
        if self._error is not None:
            return pal.red, pal.red_ring
        if self._focused:
            return pal.primary, None
        return self._border, None

    def paint_content(self, painter: QPainter, box: QRectF) -> None:
        """Рисует содержимое рамки (переопределяется)."""

    def frame_pressed(self, event) -> None:
        """Нажатие мышью на рамку (переопределяется)."""

    @property
    def frame(self) -> QWidget:
        """Виджет рамки (к нему привязывается выпадающий список)."""
        return self._frame

    def set_focused(self, focused: bool) -> None:
        """Подсвечивает рамку, пока в поле стоит курсор."""
        self._focused = focused
        self._frame.update()


class _IconSlot(QWidget):
    """Значок внутри рамки (лупа, стрелка, «глаз»)."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self.setFixedSize(ICON_SIZE, ICON_SIZE)

    def set_name(self, name: str) -> None:
        self._name = name
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        begin(painter)
        painter.drawPixmap(0, 0, icon_pixmap(self._name, ICON_SIZE, palette().ink_3))


MENU_RADIUS = 12


def menu_style() -> str:
    """Оформление всплывающего меню под цвета выбранной темы."""
    pal = palette()
    return (
        f"QMenu {{ background: {pal.card}; border: 1px solid {pal.line};"
        f" border-radius: {MENU_RADIUS}px; padding: 6px; }}"
        f"QMenu::item {{ color: {pal.ink}; padding: 8px 28px 8px 14px;"
        " border-radius: 8px; margin: 1px 0; }"
        f"QMenu::item:selected {{ background: {pal.primary_soft};"
        f" color: {pal.primary_ink}; }}"
        f"QMenu::item:disabled {{ color: {pal.ink_3}; }}"
        f"QMenu::separator {{ height: 1px; background: {pal.line_soft};"
        " margin: 4px 8px; }"
    )


def build_edit_menu(owner: QWidget, entries) -> QMenu:
    """Собирает меню «Вырезать, Копировать, Вставить» в цветах темы приложения.

    Меню светлое в светлой теме и тёмное в тёмной, а не по настройкам системы.

    Args:
        owner: Поле, для которого открыто меню.
        entries: Пункты: (подпись, действие, доступен ли) или None для черты.
    """
    menu = QMenu(owner)
    menu.setWindowFlags(
        menu.windowFlags()
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.NoDropShadowWindowHint
    )
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    menu.setFont(font("body"))
    menu.setStyleSheet(menu_style())
    for entry in entries:
        if entry is None:
            menu.addSeparator()
            continue
        title, action, enabled = entry
        item = QAction(title, menu)
        item.setEnabled(enabled)
        item.triggered.connect(action)
        menu.addAction(item)
    return menu


def show_edit_menu(owner: QWidget, position, entries) -> None:
    """Показывает меню правой кнопки мыши в точке ``position``."""
    build_edit_menu(owner, entries).exec(position)


class _Edit(QLineEdit):
    """Однострочный ввод без рамки. Скрытый текст можно копировать как есть."""

    focus_changed = Signal(bool)

    def __init__(self, masked: bool) -> None:
        super().__init__()
        self._masked = masked
        self.setFrame(False)

    def set_masked(self, masked: bool) -> None:
        self._masked = masked
        self.setEchoMode(
            QLineEdit.EchoMode.Password if masked else QLineEdit.EchoMode.Normal
        )

    def _copy_real_text(self) -> None:
        """Кладёт в буфер настоящий выделенный текст, а не точки."""
        if self.hasSelectedText():
            QGuiApplication.clipboard().setText(self.selectedText())

    def keyPressEvent(self, event) -> None:
        if self._masked and event.matches(QKeySequence.StandardKey.Copy):
            self._copy_real_text()
            event.accept()
        elif self._masked and event.matches(QKeySequence.StandardKey.Cut):
            self._copy_real_text()
            if not self.isReadOnly():
                self.del_()
            event.accept()
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.focus_changed.emit(False)

    def contextMenuEvent(self, event) -> None:
        editable = not self.isReadOnly()
        selected = self.hasSelectedText()
        show_edit_menu(
            self,
            event.globalPos(),
            (
                ("Вырезать", self._cut, editable and selected),
                ("Копировать", self._copy_real_text, selected),
                ("Вставить", self.paste, editable),
                None,
                ("Выделить всё", self.selectAll, True),
            ),
        )

    def _cut(self) -> None:
        self._copy_real_text()
        self.del_()


class _Area(QPlainTextEdit):
    """Многострочный ввод без рамки."""

    focus_changed = Signal(bool)

    def contextMenuEvent(self, event) -> None:
        editable = not self.isReadOnly()
        selected = self.textCursor().hasSelection()
        show_edit_menu(
            self,
            event.globalPos(),
            (
                ("Вырезать", self.cut, editable and selected),
                ("Копировать", self.copy, selected),
                ("Вставить", self.paste, editable),
                None,
                ("Выделить всё", self.selectAll, True),
            ),
        )

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self.focus_changed.emit(True)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self.focus_changed.emit(False)


class TextField(LabeledBox):
    """Поле ввода текста.

    Умеет показывать подсказку в пустом поле, скрывать пароль с кнопкой
    «глаз», показывать значки слева и справа, быть многострочным и
    только для чтения.
    """

    def __init__(
        self,
        label_text: Optional[str] = None,
        placeholder: str = "",
        required: bool = False,
        password: bool = False,
        trailing_icon: Optional[str] = None,
        leading_icon: Optional[str] = None,
        multiline: bool = False,
        readonly: bool = False,
        compact: bool = False,
        on_change: Optional[Callable[[], None]] = None,
        width: Optional[int] = None,
        justify: str = "left",
        parent: Optional[QWidget] = None,
    ) -> None:
        """Создаёт поле.

        Args:
            label_text: Подпись над полем.
            placeholder: Серая подсказка в пустом поле.
            required: Добавить красную звёздочку к подписи.
            password: Скрывать вводимые символы.
            trailing_icon: Значок справа (для паролей кнопка «глаз» ставится сама).
            leading_icon: Значок слева (например, лупа в поиске).
            multiline: Многострочное поле высотой в несколько строк.
            readonly: Только чтение: текст нельзя изменить.
            compact: Вид поля на панели фильтров.
            on_change: Вызывается после каждого изменения текста пользователем.
            width: Ширина поля (по умолчанию на всю ширину родителя).
            justify: Выравнивание текста в однострочном поле: ``left`` или ``center``.
            parent: Родитель.
        """
        super().__init__(
            label_text,
            required,
            height=AREA_HEIGHT if multiline else theme.CONTROL_HEIGHT,
            compact=compact,
            width=width,
            parent=parent,
        )
        pal = palette()
        self._password = password
        self._multiline = multiline
        self._readonly = readonly
        self._on_change = on_change
        self._revealed = False
        if leading_icon:
            self.content.addWidget(_IconSlot(leading_icon))
        if multiline:
            self._entry = _Area()
            self._entry.setPlaceholderText(placeholder)
            self._entry.setReadOnly(readonly)
            self._entry.setFrameShape(_Area.Shape.NoFrame)
            self.content.setContentsMargins(
                RING_PAD + TEXT_INSET,
                RING_PAD + AREA_PADDING_TOP,
                RING_PAD + TEXT_INSET,
                RING_PAD + AREA_PADDING_TOP,
            )
            self._entry.textChanged.connect(self._notify_area)
        else:
            self._entry = _Edit(password)
            self._entry.setPlaceholderText(placeholder)
            self._entry.setReadOnly(readonly)
            if password:
                self._entry.setEchoMode(QLineEdit.EchoMode.Password)
            if justify == "center":
                self._entry.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._entry.textEdited.connect(self._on_edited)
        self._entry.setFont(font("body"))
        self._style_entry(pal)
        self._entry.focus_changed.connect(self.set_focused)
        self._entry.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.content.addWidget(self._entry, 1)
        self._trailing: Optional[_IconSlot] = None
        trailing = "eye" if password else trailing_icon
        if trailing:
            self._trailing = _IconSlot(trailing)
            self.content.addWidget(self._trailing)
            if password:
                clickable(self._trailing, self._toggle_reveal)
        self.setFocusProxy(self._entry)

    def _style_entry(self, pal) -> None:
        self._entry.setStyleSheet(
            "background: transparent; border: none; padding: 0; "
            f"selection-background-color: {pal.primary_soft}; "
            f"selection-color: {pal.ink}; "
            # Точки пароля те же, что были в макете: маленькая «•», а не крупный круг.
            f"lineedit-password-character: {ord(MASK_CHAR)};"
        )
        recolor(self._entry, "ink_3" if self._readonly else "ink")
        colors = self._entry.palette()
        colors.setColor(colors.ColorRole.PlaceholderText, QColor(pal.ink_3))
        self._entry.setPalette(colors)

    # --- текст ---

    @property
    def entry(self) -> QWidget:
        """Внутренний виджет ввода (для порядка фокуса и событий)."""
        return self._entry

    def get(self) -> str:
        """Возвращает введённый текст."""
        if self._multiline:
            return self._entry.toPlainText()
        return self._entry.text()

    def set(self, value: str) -> None:
        """Записывает текст в поле (обработчик изменения не вызывается)."""
        if self._multiline:
            self._entry.blockSignals(True)
            self._entry.setPlainText(value)
            self._entry.blockSignals(False)
        else:
            self._entry.setText(value)

    def focus_field(self) -> None:
        """Переводит фокус в поле."""
        self._entry.setFocus()

    def connect_edited(self, slot: Callable[[str], None]) -> None:
        """Вызывает функцию после каждой правки текста пользователем."""
        if self._multiline:
            self._entry.textChanged.connect(lambda: slot(self.get()))
        else:
            self._entry.textEdited.connect(slot)

    def connect_blur(self, slot: Callable[[], None]) -> None:
        """Вызывает функцию, когда пользователь ушёл с поля (потеря фокуса)."""
        self._entry.focus_changed.connect(lambda focused: None if focused else slot())

    def bind_submit(self, command: Callable[[], None]) -> None:
        """Вызывает команду по нажатию Enter в однострочном поле."""
        if not self._multiline:
            self._entry.returnPressed.connect(command)

    # --- пароль и события ---

    @property
    def revealed(self) -> bool:
        """Показан ли пароль открытым текстом."""
        return self._revealed

    def _toggle_reveal(self) -> None:
        self._revealed = not self._revealed
        self._entry.set_masked(not self._revealed)
        if self._trailing is not None:
            self._trailing.set_name("eye-off" if self._revealed else "eye")

    def frame_pressed(self, _event) -> None:
        """Нажатие на край рамки (вне самого ввода) ставит курсор в поле."""
        self._entry.setFocus()

    def _on_edited(self, _text: str) -> None:
        self.clear_error()
        if self._on_change is not None:
            self._on_change()

    def _notify_area(self) -> None:
        self.clear_error()
        if self._on_change is not None:
            self._on_change()
