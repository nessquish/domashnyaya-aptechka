"""Окно приложения: переключение экранов и вход пользователя."""

from typing import Callable, Optional

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QMainWindow, QStackedLayout, QWidget

from pharmacy.db.connection import Database
from pharmacy.errors import NotFoundError
from pharmacy.models import User
from pharmacy.ui import runtime
from pharmacy.ui.screens.auth import LoginScreen, RegisterScreen
from pharmacy.ui.screens.shell import TEXT_SIZE, MainShell
from pharmacy.services.container import Services, build_services
from pharmacy.ui import sections, theme
from pharmacy.ui.scaling import apply_scale_factor
from pharmacy.ui.preferences import Preferences
from pharmacy.ui.remember import REMEMBER_FILE, RememberedLogin

WINDOW_TITLE = "Моя аптечка"
PREFERENCES_FILE = "preferences.json"  # лежит рядом с файлом базы
ScreenFactory = Callable[["App"], QWidget]


class App(QMainWindow):
    """Главное окно. Хранит сервисы и вошедшего пользователя.

    Attributes:
        services: Все сервисы приложения.
        user: Вошедший пользователь или None на экранах входа.
        session_password: Пароль, введённый при входе (только в памяти).
        preferences: Предпочтения отображения (размер текста, боковая панель).
    """

    def __init__(
        self,
        services: Services,
        preferences: Optional[Preferences] = None,
        remembered: Optional[RememberedLogin] = None,
    ) -> None:
        """Создаёт окно по размеру макета и показывает экран входа.

        Args:
            services: Сервисы приложения.
            preferences: Предпочтения отображения. По умолчанию хранятся
                только в памяти.
        """
        runtime.application()
        super().__init__()
        self.services = services
        self.preferences = preferences or Preferences()
        self.remembered = remembered or RememberedLogin()
        self.user: Optional[User] = None
        self.session_password = ""
        self._screen: Optional[QWidget] = None
        theme.set_theme(runtime.system_theme())
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(runtime.app_icon())
        self.setMinimumSize(theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT)
        self.resize(theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT)
        self._stack = QStackedLayout()
        central = QWidget()
        central.setLayout(self._stack)
        self.setCentralWidget(central)
        self._paint_background()
        self._center()
        self.show_login()

    @property
    def screen_widget(self) -> Optional[QWidget]:
        """Экран, который показан сейчас."""
        return self._screen

    def _paint_background(self) -> None:
        """Красит окно в цвет фона темы."""
        colors = self.palette()
        colors.setColor(QPalette.ColorRole.Window, QColor(theme.palette().bg))
        self.setPalette(colors)
        self.setAutoFillBackground(True)

    def show_screen(self, factory: ScreenFactory) -> None:
        """Заменяет текущий экран новым.

        Новый экран строится целиком, пока старый ещё на виду, и подменяет его
        за один кадр: промежуточных состояний пользователь не видит.

        Args:
            factory: Класс или функция, создающие экран по окну.
        """
        self._paint_background()
        screen = factory(self)
        old = self._screen
        self._stack.addWidget(screen)
        self._stack.setCurrentWidget(screen)
        self._screen = screen
        if old is not None:
            self._stack.removeWidget(old)
            old.hide()
            old.deleteLater()

    def show_login(self) -> None:
        """Показывает экран входа."""
        self.show_screen(LoginScreen)

    def show_register(self) -> None:
        """Показывает экран регистрации."""
        self.show_screen(RegisterScreen)

    def sign_in(self, user: User, password: str = "", remember: bool = False) -> None:
        """Запоминает вошедшего пользователя, применяет его тему и открывает аптечку.

        Args:
            user: Вошедший пользователь.
            password: Пароль, который он ввёл. Хранится только в памяти до
                выхода (для показа в настройках), на диск не записывается.
            remember: Запомнить устройство на 30 дней.
        """
        if remember:
            self.remembered.remember(user.id, user.password_hash)
        self.user = user
        self.session_password = password
        self._apply_view_settings(user)
        self.services.notifications.refresh(user.id)
        self.show_screen(MainShell)

    def restore_session(self) -> bool:
        """Входит без пароля, если устройство запомнено и срок не истёк.

        Returns:
            True, если вход выполнен.
        """
        user_id = self.remembered.user_id()
        if user_id is None:
            return False
        try:
            user = self.services.settings.get_user(user_id)
        except NotFoundError:
            self.remembered.clear()
            return False
        if not self.remembered.matches(user.password_hash):
            self.remembered.clear()
            return False
        self.sign_in(user)
        return True

    def apply_user_changes(
        self, user: User, notice: str = "", start: str = sections.SETTINGS
    ) -> None:
        """Применяет изменённые данные или тему пользователя и перестраивает окно.

        Нужно после сохранения настроек или смены темы: имя в боковом меню и
        цвета темы читаются при создании виджетов, поэтому окно строится заново.

        Args:
            user: Пользователь с новыми данными.
            notice: Сообщение для открывшегося экрана.
            start: Раздел, который открывается после перестроения.
        """
        self.user = user
        self._apply_view_settings(user)
        self.show_screen(lambda app: MainShell(app, start=start, notice=notice))

    def _apply_view_settings(self, user: User) -> None:
        """Включает тему и размер текста пользователя до построения экранов."""
        theme.set_theme(user.theme)
        size = self.preferences.get(user.id, TEXT_SIZE, theme.DEFAULT_TEXT_SIZE)
        theme.set_text_size(
            size if size in theme.TEXT_SIZES else theme.DEFAULT_TEXT_SIZE
        )
        self._fit_window()

    def _fit_window(self) -> None:
        """Подгоняет минимальную ширину окна под размер текста.

        Если окно уже, чем нужно, оно расширяется (но не шире экрана).
        """
        screen_width, _ = runtime.screen_size()
        width = min(theme.window_width(), screen_width - 40)
        self.setMinimumSize(width, theme.WINDOW_HEIGHT)
        if self.width() < width:
            self.resize(width, max(self.height(), theme.WINDOW_HEIGHT))

    def sign_out(self) -> None:
        """Выходит из аккаунта и возвращается на экран входа."""
        self.user = None
        self.session_password = ""
        self.remembered.clear()
        theme.set_theme(runtime.system_theme())
        theme.set_text_size(theme.DEFAULT_TEXT_SIZE)
        self.setMinimumSize(theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT)
        self.show_login()

    def _center(self) -> None:
        """Ставит окно по центру экрана."""
        screen_width, screen_height = runtime.screen_size()
        self.move(
            max((screen_width - self.width()) // 2, 0),
            max((screen_height - self.height()) // 2, 0),
        )


def run(db: Optional[Database] = None) -> None:
    """Запускает приложение.

    Args:
        db: База данных. Если не задана, используется файл из настроек.
    """
    apply_scale_factor()
    application = runtime.application()
    db = db or Database()
    db.init_schema()
    preferences = Preferences(db.path.parent / PREFERENCES_FILE)
    remembered = RememberedLogin(db.path.parent / REMEMBER_FILE)
    window = App(build_services(db), preferences, remembered)
    window.restore_session()
    window.show()
    application.exec()
