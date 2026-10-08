"""Боковое меню: разделы, счётчик уведомлений, пользователь и выход."""

from typing import Callable, Dict, Optional, Sequence

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pharmacy.models import User
from pharmacy.ui.fonts import font, line_height, text_width
from pharmacy.ui.icons import icon_pixmap
from pharmacy.ui.paint import Shadow, begin, draw_shadows, fill_rounded, qcolor
from pharmacy.ui.widgets.common import clickable, label
from pharmacy.ui.widgets.iconbutton import IconButton
from pharmacy.ui import theme
from pharmacy.ui.theme import mix, palette

NAV_RADIUS = 10
NAV_PAD = 3  # поле под тень выбранного пункта
NAV_PADDING_X = 12
NAV_PADDING_Y = 9
COUNTER_PADDING_X = 7
COUNTER_PADDING_Y = 1
AVATAR_SIZE = 26
LINK_ICON = 14
NAV_ICON = 16
NAV_ICON_GAP = 10
LINK_GAP = 8


class NavItem(QAbstractButton):
    """Пункт меню: название, выделение выбранного и необязательный счётчик."""

    def __init__(
        self,
        text: str,
        command: Callable[[], None],
        parent: Optional[QWidget] = None,
        icon: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setText(text)
        self._icon = icon
        self._active = False
        self._count = 0
        self._height = line_height("body") + 2 * NAV_PADDING_Y
        self.setFixedHeight(self._height + 2 * NAV_PAD)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(lambda _checked=False: command())

    @property
    def active(self) -> bool:
        """Выбран ли пункт."""
        return self._active

    @property
    def count(self) -> int:
        """Число на счётчике справа (0 если счётчика нет)."""
        return self._count

    def set_active(self, active: bool) -> None:
        """Выделяет пункт как выбранный или снимает выделение."""
        self._active = active
        self.update()

    def set_count(self, count: int) -> None:
        """Показывает счётчик справа (0 скрывает его)."""
        self._count = count
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(100, self._height + 2 * NAV_PAD)

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        begin(painter)
        body = QRectF(NAV_PAD, NAV_PAD, self.width() - 2 * NAV_PAD, self._height)
        if self._active:
            fill, ink, style = pal.primary_soft, pal.primary_ink, "body_strong"
            draw_shadows(painter, body, NAV_RADIUS, (Shadow(2, 6, pal.primary, 0.18),))
            fill_rounded(painter, body, NAV_RADIUS, fill)
        else:
            ink, style = pal.ink_2, "body"
            if self.underMouse():
                fill_rounded(
                    painter, body, NAV_RADIUS, mix(pal.side, pal.primary_soft, 0.5)
                )
        left = NAV_PAD + NAV_PADDING_X
        if self._icon:
            painter.drawPixmap(
                round(left),
                round(body.center().y() - NAV_ICON / 2),
                icon_pixmap(self._icon, NAV_ICON, ink),
            )
            left += NAV_ICON + NAV_ICON_GAP
        painter.setFont(font(style))
        painter.setPen(qcolor(ink))
        painter.drawText(
            QRectF(left, body.top(), body.width(), body.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.text(),
        )
        if self._count:
            self._paint_counter(painter, body)

    def _paint_counter(self, painter: QPainter, body: QRectF) -> None:
        pal = palette()
        text = str(self._count)
        width = text_width(text, "counter") + 2 * COUNTER_PADDING_X
        height = line_height("counter") + 2 * COUNTER_PADDING_Y
        right = self.width() - NAV_PAD - NAV_PADDING_X
        chip = QRectF(right - width, body.center().y() - height / 2, width, height)
        fill_rounded(painter, chip, theme.BADGE_RADIUS, pal.primary)
        painter.setFont(font("counter"))
        painter.setPen(qcolor(pal.on_primary))
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, text)

    def enterEvent(self, event) -> None:
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.update()
        super().leaveEvent(event)


class _Avatar(QWidget):
    """Круг с первой буквой имени пользователя."""

    def __init__(self, letter: str) -> None:
        super().__init__()
        self._letter = letter
        self.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        begin(painter)
        box = QRectF(0, 0, AVATAR_SIZE, AVATAR_SIZE)
        fill_rounded(painter, box, AVATAR_SIZE / 2, pal.primary)
        painter.setFont(font("counter"))
        painter.setPen(qcolor(pal.on_primary))
        painter.drawText(box, Qt.AlignmentFlag.AlignCenter, self._letter)


class _FooterLink(QAbstractButton):
    """Строка внизу меню: значок и подпись, нажатие вызывает команду."""

    def __init__(
        self, text: str, icon: str, color: str, command: Callable[[], None]
    ) -> None:
        super().__init__()
        self.setText(text)
        self._icon = icon
        self._color = color
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(max(line_height("body"), LINK_ICON) + 8)
        self.clicked.connect(lambda _checked=False: command())

    def sizeHint(self) -> QSize:
        return QSize(100, self.height())

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        begin(painter)
        top = round((self.height() - LINK_ICON) / 2)
        painter.drawPixmap(0, top, icon_pixmap(self._icon, LINK_ICON, self._color))
        painter.setFont(font("body"))
        painter.setPen(qcolor(self._color))
        painter.drawText(
            QRectF(LINK_ICON + LINK_GAP, 0, self.width(), self.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.text(),
        )


class _Line(QWidget):
    """Тонкая горизонтальная линия."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(1)

    def paintEvent(self, _event) -> None:
        QPainter(self).fillRect(self.rect(), palette().line)


class Sidebar(QFrame):
    """Левая панель: название, разделы, пользователь и кнопка выхода."""

    def __init__(
        self,
        user: User,
        sections: Sequence[str],
        on_select: Callable[[str], None],
        on_logout: Callable[[], None],
        on_toggle_theme: Callable[[], None],
        on_collapse: Callable[[], None],
        parent: Optional[QWidget] = None,
        icons: Optional[Dict[str, str]] = None,
        on_profile: Optional[Callable[[], None]] = None,
        on_search: Optional[Callable[[], None]] = None,
    ) -> None:
        """Создаёт меню.

        Args:
            user: Вошедший пользователь (имя и логин внизу).
            sections: Названия разделов сверху вниз.
            on_select: Вызывается с названием раздела при нажатии.
            on_logout: Вызывается при нажатии на «Выход».
            on_toggle_theme: Вызывается при нажатии на «Тёмная/Светлая тема».
            on_collapse: Вызывается при нажатии на кнопку сворачивания панели.
            parent: Родитель.
            icons: Значки пунктов по названию раздела (None: без значков).
            on_profile: Вызывается при нажатии на аватар и имя пользователя.
            on_search: Вызывается при нажатии на лупу (поиск по программе).
        """
        super().__init__(parent)
        pal = palette()
        self.setFixedWidth(theme.sidebar_width())
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)
        colors = self.palette()
        colors.setColor(colors.ColorRole.Window, qcolor(pal.side))
        self.setPalette(colors)
        self.backdrop_color = pal.side
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14 - NAV_PAD, 0, 14 - NAV_PAD + 1, 0)
        outer.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(NAV_PAD + 4, 18 + theme.TOP_OFFSET, NAV_PAD, 22)
        header.addWidget(label("Моя аптечка", "sidebar_title", "brand_ink"))
        header.addStretch(1)
        header.addWidget(IconButton("panel-left", on_collapse))
        outer.addLayout(header)

        if on_search is not None:
            # Поиск по программе (Ctrl+F): первый пункт над разделами.
            self.search_button = NavItem("Поиск", on_search, icon="search")
            outer.addWidget(self.search_button)

        self._items: Dict[str, NavItem] = {}
        for name in sections:
            item = NavItem(
                name,
                lambda value=name: on_select(value),
                icon=(icons or {}).get(name),
            )
            outer.addWidget(item)
            self._items[name] = item
        outer.addStretch(1)
        self._build_footer(outer, user, on_logout, on_toggle_theme, on_profile)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.fillRect(self.width() - 1, 0, 1, self.height(), palette().line)

    def set_active(self, name: str) -> None:
        """Выделяет раздел в меню."""
        for key, item in self._items.items():
            item.set_active(key == name)

    def set_count(self, name: str, count: int) -> None:
        """Показывает счётчик у раздела."""
        self._items[name].set_count(count)

    def item(self, name: str) -> NavItem:
        """Пункт меню по названию раздела."""
        return self._items[name]

    def _build_footer(
        self,
        outer: QVBoxLayout,
        user: User,
        on_logout: Callable[[], None],
        on_toggle_theme: Callable[[], None],
        on_profile: Optional[Callable[[], None]] = None,
    ) -> None:
        pal = palette()
        line = _Line()
        line_row = QHBoxLayout()
        line_row.setContentsMargins(NAV_PAD, 0, NAV_PAD, 0)
        line_row.addWidget(line)
        outer.addLayout(line_row)

        # Нажатие на аватар и имя открывает профиль пользователя.
        self.profile = QWidget()
        person = QHBoxLayout(self.profile)
        person.setContentsMargins(NAV_PAD + 8, 14, NAV_PAD + 8, 6)
        person.setSpacing(8)
        person.addWidget(_Avatar(user.username[:1].upper()))
        names = QVBoxLayout()
        names.setContentsMargins(0, 0, 0, 0)
        names.setSpacing(0)
        names.addWidget(label(user.username, "user_name", tight=True))
        names.addWidget(label(user.login, "caption", "ink_3", tight=True))
        person.addLayout(names)
        person.addStretch(1)
        outer.addWidget(self.profile)
        if on_profile is not None:
            clickable(self.profile, on_profile)

        dark = theme.theme_name() == theme.DARK_THEME
        self.theme_link = _FooterLink(
            "Светлая тема" if dark else "Тёмная тема",
            "sun" if dark else "moon",
            pal.ink_2,
            on_toggle_theme,
        )
        self.logout_link = _FooterLink("Выход", "logout", pal.red, on_logout)
        for link, bottom in ((self.theme_link, 4), (self.logout_link, 14 - NAV_PAD)):
            row = QHBoxLayout()
            row.setContentsMargins(NAV_PAD + 12, 0, NAV_PAD + 12, bottom)
            row.addWidget(link)
            outer.addLayout(row)
