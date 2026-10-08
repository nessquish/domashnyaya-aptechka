"""Оболочка главного окна: боковое меню и область с выбранным разделом."""

from typing import TYPE_CHECKING, Callable, Dict, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from PySide6.QtGui import QColor, QPainter

from pharmacy.errors import NotFoundError
from pharmacy.models import User
from pharmacy.ui.screens.dashboard import DashboardScreen
from pharmacy.ui.screens.history import HistoryScreen
from pharmacy.ui.screens.my_kit import MyKitScreen
from pharmacy.ui.screens.notifications import NotificationsScreen
from pharmacy.ui.screens.product_card import ProductCardDialog
from pharmacy.ui.screens.product_form import ProductFormDialog
from pharmacy.ui.screens.settings import SettingsScreen
from pharmacy.ui.screens.shopping import ShoppingScreen
from pharmacy.ui.widgets.dialog import Dialog
from pharmacy.ui.widgets.iconbutton import IconButton
from pharmacy.ui.widgets.scroll import ScrollArea
from pharmacy.ui.widgets.sidebar import Sidebar
from pharmacy.services.container import Services
from pharmacy.services.status import ProductStatus
from pharmacy.ui import sections, theme
from pharmacy.ui.preferences import MENU_ICONS
from pharmacy.ui.theme import CARD_SHADOW_PAD, palette

if TYPE_CHECKING:
    from pharmacy.ui.app import App

ScreenFactory = Callable[["MainShell"], QWidget]

RAIL_WIDTH = 44  # ширина полосы, которая остаётся от свёрнутой боковой панели
SIDEBAR_COLLAPSED = "sidebar_collapsed"  # ключи в предпочтениях пользователя
TEXT_SIZE = "text_size"
THEME_MODE = "theme_mode"  # light, dark или system (как в операционной системе)

# Содержимое окна отступает от краёв на отступ макета минус поле под тень карточек.
CONTENT_PADDING_X = theme.CONTENT_PADDING_X - CARD_SHADOW_PAD


class _Rail(QFrame):
    """Узкая полоса с кнопкой «развернуть», которая остаётся от свёрнутой панели."""

    def __init__(self, on_expand: Callable[[], None]) -> None:
        super().__init__()
        self.setFixedWidth(RAIL_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.backdrop_color = palette().side
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 18 + theme.TOP_OFFSET, 1, 0)
        layout.addWidget(
            IconButton("panel-left", on_expand), 0, Qt.AlignmentFlag.AlignHCenter
        )
        layout.addStretch(1)

    def paintEvent(self, _event) -> None:
        pal = palette()
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(pal.side))
        painter.fillRect(self.width() - 1, 0, 1, self.height(), QColor(pal.line))


class MainShell(QWidget):
    """Главное окно после входа.

    Attributes:
        app: Окно приложения.
        user: Вошедший пользователь.
        services: Сервисы приложения.
        notice: Сообщение для первого открытого экрана (например, «сохранено»).
            Экран забирает его и очищает.
        section: Название открытого раздела.
    """

    def __init__(
        self,
        app: "App",
        start: str = sections.HOME,
        notice: str = "",
    ) -> None:
        """Создаёт оболочку и открывает стартовый раздел.

        Args:
            app: Окно приложения.
            start: Раздел, который открывается первым.
            notice: Сообщение для стартового экрана.
        """
        super().__init__()
        self.app = app
        self.user: User = app.user
        self.services: Services = app.services
        self.notice = notice
        self.backdrop_color = palette().bg
        self._sections: Dict[str, ScreenFactory] = {
            sections.HOME: DashboardScreen,
            sections.MY_KIT: MyKitScreen,
            sections.SHOPPING: ShoppingScreen,
            sections.NOTIFICATIONS: NotificationsScreen,
            sections.HISTORY: HistoryScreen,
            sections.SETTINGS: SettingsScreen,
        }
        self._current: Optional[QWidget] = None
        self.section = start
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self._sidebar = Sidebar(
            self.user,
            sections.ALL,
            self.navigate,
            self.confirm_logout,
            self.toggle_theme,
            lambda: self.set_sidebar_collapsed(True),
            icons=(
                sections.ICONS
                if self.app.preferences.get(self.user.id, MENU_ICONS, True)
                else None
            ),
        )
        self._rail = _Rail(lambda: self.set_sidebar_collapsed(False))
        self._scroll = ScrollArea(gutter=CONTENT_PADDING_X)
        self._collapsed = bool(
            self.app.preferences.get(self.user.id, SIDEBAR_COLLAPSED, False)
        )
        row.addWidget(self._sidebar)
        row.addWidget(self._rail)
        self._sidebar.setVisible(not self._collapsed)
        self._rail.setVisible(self._collapsed)
        content = QVBoxLayout()
        content.setContentsMargins(CONTENT_PADDING_X, theme.CONTENT_PADDING_Y, 0, 0)
        content.addWidget(self._scroll)
        row.addLayout(content, 1)
        self.navigate(start)

    def viewport_height(self) -> int:
        """Высота видимой области раздела."""
        return self._scroll.viewport().height()

    @property
    def current(self) -> Optional[QWidget]:
        """Экран открытого раздела."""
        return self._current

    @property
    def sidebar(self) -> Sidebar:
        """Боковое меню."""
        return self._sidebar

    @property
    def sidebar_collapsed(self) -> bool:
        """Свёрнута ли боковая панель."""
        return self._collapsed

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        fit = getattr(self._current, "fit_rows", None)
        if fit is not None:
            QTimer.singleShot(0, fit)

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        """Сворачивает или разворачивает боковую панель и запоминает выбор."""
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self.app.preferences.set(self.user.id, SIDEBAR_COLLAPSED, collapsed)
        self._sidebar.setVisible(not collapsed)
        self._rail.setVisible(collapsed)

    def set_text_size(self, name: str) -> None:
        """Запоминает размер текста и сразу применяет его (окно строится заново)."""
        if name == theme.text_size_name():
            return
        self.app.preferences.set(self.user.id, TEXT_SIZE, name)
        self.app.apply_user_changes(self.user, start=self.section)

    def navigate(self, name: str) -> None:
        """Открывает раздел и выделяет его в меню.

        Raises:
            ValueError: Если такого раздела нет.
        """
        factory = self._sections.get(name)
        if factory is None:
            raise ValueError(f"Неизвестный раздел: {name}")
        self.show_screen(factory, name)

    def show_screen(self, factory: ScreenFactory, section: str) -> None:
        """Показывает экран в области содержимого.

        Экран строится целиком, пока прежний ещё на виду, а затем подменяет его.

        Args:
            factory: Создаёт экран по оболочке.
            section: Раздел меню, который остаётся выделенным (карточка товара
                относится к разделу «Моя аптечка»).
        """
        screen = factory(self)
        old = self._current
        self._scroll.setUpdatesEnabled(False)
        try:
            self._scroll.body.addWidget(screen)
            if old is not None:
                self._scroll.body.removeWidget(old)
                old.hide()
                old.deleteLater()
            self._current = screen
            self._scroll.scroll_to_top()
        finally:
            self._scroll.setUpdatesEnabled(True)
        self.section = section
        self._sidebar.set_active(section)
        self.refresh_counters()

    def open_kit(self, status: Optional[ProductStatus] = None) -> None:
        """Открывает «Мою аптечку», при необходимости сразу с фильтром по состоянию."""
        self.show_screen(lambda shell: MyKitScreen(shell, status), sections.MY_KIT)

    def open_shopping(self, tab: int = 0) -> None:
        """Открывает список покупок на нужной вкладке."""
        self.show_screen(lambda shell: ShoppingScreen(shell, tab), sections.SHOPPING)

    def refresh(self) -> None:
        """Перестраивает открытый раздел, чтобы в нём были свежие данные."""
        self.navigate(self.section)

    def open_product(self, product_id: int) -> None:
        """Открывает карточку товара окном поверх текущего экрана."""
        try:
            ProductCardDialog(self, product_id)
        except NotFoundError:  # товар уже удалён
            self.refresh()

    def edit_product(self, product_id: int) -> None:
        """Открывает окно редактирования товара поверх текущего экрана.

        После сохранения раздел обновляется и снова открывается карточка. Если
        окно закрыли кнопкой «Отмена», карточка открывается как была.
        """

        def saved(view) -> None:
            self.refresh()
            if view is not None:
                self.open_product(product_id)

        try:
            dialog = ProductFormDialog(
                self.app, self.services, self.user.id, saved, product_id
            )
        except NotFoundError:
            self.refresh()
            return
        dialog.on_cancel(lambda: self.open_product(product_id))

    def add_product(self) -> None:
        """Сразу открывает окно добавления товара поверх текущего экрана.

        После сохранения показывается «Моя аптечка»: товар стоит в таблице там,
        куда его ставит выбранная сортировка (если сортировку не выбирали, по
        состоянию), и таблица открыта на нужной странице.
        """

        def saved(view) -> None:
            self.navigate(sections.MY_KIT)
            if view is not None and isinstance(self.current, MyKitScreen):
                self.current.reveal(view.product.id)

        ProductFormDialog(self.app, self.services, self.user.id, saved)

    def set_theme(self, name: str) -> None:
        """Сохраняет тему в настройках пользователя и сразу применяет её.

        Окно строится заново на том же разделе: цвета читаются при создании
        виджетов.
        """
        if name == self.app.theme_mode(self.user):
            return
        self.app.preferences.set(self.user.id, THEME_MODE, name)
        resolved = self.app.resolve_theme(self.user)
        user = self.user
        if resolved != user.theme:
            user = self.services.settings.update_settings(
                user.id,
                str(user.warning_days),
                resolved,
                user.notify_expired,
                user.notify_low_stock,
            )
        self.app.apply_user_changes(user, start=self.section)

    def toggle_theme(self) -> None:
        """Переключает светлую и тёмную тему."""
        dark = theme.theme_name() == theme.DARK_THEME
        self.set_theme(theme.LIGHT_THEME if dark else theme.DARK_THEME)

    def take_notice(self) -> str:
        """Отдаёт сообщение для экрана и очищает его."""
        notice, self.notice = self.notice, ""
        return notice

    def refresh_counters(self) -> None:
        """Обновляет счётчик непрочитанных уведомлений в меню."""
        unread = self.services.notifications.count_unread(self.user.id)
        self._sidebar.set_count(sections.NOTIFICATIONS, unread)

    def confirm_logout(self) -> None:
        """Спрашивает подтверждение и выходит из аккаунта."""
        Dialog(
            self.app,
            "Выйти из аккаунта?",
            "Чтобы снова открыть аптечку, нужно будет ввести логин и пароль.",
            "Выйти",
            self.app.sign_out,
            width=360,
        )
