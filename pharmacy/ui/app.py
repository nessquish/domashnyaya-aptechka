"""Окно приложения: переключение экранов и вход пользователя."""

from typing import Callable, Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import QMainWindow, QStackedLayout, QWidget

from pharmacy.db.connection import Database
from pharmacy.errors import NotFoundError
from pharmacy.models import User
from pharmacy.ui import runtime
from pharmacy.ui.screens.auth import LoginScreen, RegisterScreen
from pharmacy.ui.screens.search import SearchModal
from pharmacy.ui.screens.shell import TEXT_SIZE, THEME_MODE, MainShell
from pharmacy.ui.search_index import Target
from pharmacy.services.container import Services, build_services
from pharmacy.ui import sections, theme
from pharmacy.config import is_demo_build
from pharmacy.ui.scaling import apply_scale_factor
from pharmacy.services.notification_service import NotifyOptions
from pharmacy.ui.preferences import (
    GLOBAL_USER,
    SCALE_MODE,
    SCALE_PERCENT,
    Preferences,
)
from pharmacy.ui.remember import REMEMBER_FILE, RememberedLogin

WINDOW_TITLE = "Моя аптечка"
SYSTEM_THEME = "system"
SYSTEM_THEME_CHECK_MS = 2000
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
        self.reopen_settings: Optional[str] = None  # раздел настроек после пересборки
        self.search_modal: Optional[SearchModal] = None
        services.notifications.options_for = self.notify_options
        self.user: Optional[User] = None
        self.session_password = ""
        self._screen: Optional[QWidget] = None
        theme.set_theme(runtime.system_theme())
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowIcon(runtime.app_icon())
        self.setMinimumSize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)
        self.resize(theme.WINDOW_WIDTH, theme.WINDOW_HEIGHT)
        self._stack = QStackedLayout()
        central = QWidget()
        central.setLayout(self._stack)
        self.setCentralWidget(central)
        self._paint_background()
        self._center()
        # Ctrl+F: на русской раскладке та же клавиша даёт букву «А».
        for keys in ("Ctrl+F", "Ctrl+А"):
            QShortcut(QKeySequence(keys), self, activated=self.open_search)
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
        theme.set_theme(self.resolve_theme(user))
        size = self.preferences.get(user.id, TEXT_SIZE, theme.DEFAULT_TEXT_SIZE)
        theme.set_text_size(
            size if size in theme.TEXT_SIZES else theme.DEFAULT_TEXT_SIZE
        )
        self._fit_window()

    def open_search(self) -> None:
        """Открывает окно поиска по программе (только после входа)."""
        if self.user is None or not isinstance(self._screen, MainShell):
            return
        if self.search_modal is not None and self.search_modal.is_open:
            return
        self.search_modal = SearchModal(self, self.services, self.user.id)

    def go_to(self, target: Target) -> None:
        """Переходит к найденному: открывает нужный раздел, настройку или товар."""
        if isinstance(self._screen, MainShell):
            self._screen.go_to(target)

    def notify_options(self, user_id: int) -> NotifyOptions:
        """Общие настройки уведомлений пользователя (хранятся в предпочтениях)."""
        prefs = self.preferences
        return NotifyOptions(
            enabled=bool(prefs.get(user_id, "notify_enabled", True)),
            expiring=bool(prefs.get(user_id, "notify_expiring", True)),
            low_threshold=float(prefs.get(user_id, "low_threshold", 0) or 0),
        )
        
    def theme_mode(self, user: User) -> str:
        """Тема оформления — настройка устройства, общая для всех аккаунтов.

        Хранится в preferences под ``GLOBAL_USER``. По умолчанию — системная.
        """
        mode = self.preferences.get(GLOBAL_USER, THEME_MODE, SYSTEM_THEME)
        return (
            mode
            if mode in (theme.LIGHT_THEME, theme.DARK_THEME, SYSTEM_THEME)
            else SYSTEM_THEME
        )

    def resolve_theme(self, user: User) -> str:
        """Тема, которую нужно показать: при выборе «Системная» берётся тема системы."""
        mode = self.theme_mode(user)
        return runtime.system_theme() if mode == SYSTEM_THEME else mode

    def watch_system_theme(self) -> None:
        """Раз в пару секунд проверяет тему системы и подстраивает окно."""
        self._system_timer = QTimer(self)
        self._system_timer.setInterval(SYSTEM_THEME_CHECK_MS)
        self._system_timer.timeout.connect(self._follow_system_theme)
        self._system_timer.start()

    def _follow_system_theme(self) -> None:
        wanted = runtime.system_theme()
        if self.user is None:
            if theme.theme_name() != wanted:
                theme.set_theme(wanted)
                self.show_screen(type(self._screen))
            return
        if self.theme_mode(self.user) != SYSTEM_THEME or theme.theme_name() == wanted:
            return
        user = self.services.settings.update_settings(
            self.user.id,
            str(self.user.warning_days),
            wanted,
            self.user.notify_expired,
            self.user.notify_low_stock,
        )
        section = self._screen.section if hasattr(self._screen, "section") else None
        self.apply_user_changes(user, start=section or sections.SETTINGS)

    def _fit_window(self) -> None:
        """Подгоняет минимальную ширину окна под размер текста.

        Если окно уже, чем нужно, оно расширяется (но не шире экрана).
        """
        screen_width, _ = runtime.screen_size()
        width = min(theme.window_width(), screen_width - 40)
        self.setMinimumSize(width, theme.WINDOW_MIN_HEIGHT)
        if self.width() < width:
            self.resize(width, self.height())

    def sign_out(self) -> None:
        """Выходит из аккаунта и возвращается на экран входа."""
        self.user = None
        self.session_password = ""
        self.remembered.clear()
        theme.set_theme(runtime.system_theme())
        theme.set_text_size(theme.DEFAULT_TEXT_SIZE)
        self.setMinimumSize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)
        self.show_login()

    def _center(self) -> None:
        """Ставит окно по центру экрана."""
        screen_width, screen_height = runtime.screen_size()
        self.move(
            max((screen_width - self.width()) // 2, 0),
            max((screen_height - self.height()) // 2, 0),
        )

def prepare_demo(db: Database) -> None:
    """В демо-сборке при первом запуске создаёт тестовый аккаунт со всеми данными."""
    from pharmacy.db.seed import seed_demo, seed_full

    if db.fetch_one("SELECT id FROM users LIMIT 1") is not None:
        return
    user_id = seed_demo(db)
    if user_id is not None:
        seed_full(db, user_id)


def manual_scale(preferences: Preferences) -> Optional[float]:
    """Ручной масштаб из настроек (None, если выбран автоматический)."""
    if preferences.get(GLOBAL_USER, SCALE_MODE, "auto") != "manual":
        return None
    percent = preferences.get(GLOBAL_USER, SCALE_PERCENT, 100)
    return float(percent) / 100


def run(db: Optional[Database] = None) -> None:
    """Запускает приложение.

    Args:
        db: База данных. Если не задана, используется файл из настроек.
    """
    db = db or Database()
    preferences = Preferences(db.path.parent / PREFERENCES_FILE)
    apply_scale_factor(manual_scale(preferences))
    application = runtime.application()
    db.init_schema()
    if is_demo_build():
        prepare_demo(db)
    remembered = RememberedLogin(db.path.parent / REMEMBER_FILE)
    window = App(build_services(db), preferences, remembered)
    window.restore_session()
    window.watch_system_theme()
    window.show()
    application.exec()
