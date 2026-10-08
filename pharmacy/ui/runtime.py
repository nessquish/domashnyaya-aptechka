"""Запуск Qt: приложение, шрифты, русский язык стандартных окон и значок."""

import sys
from typing import Optional

from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from pharmacy.ui import fonts
from pharmacy.ui.icons import icon_pixmap
from pharmacy.ui.paint import begin, fill_rounded
from pharmacy.ui.theme import LIGHT

ICON_SIZES = (16, 32, 48, 64, 128, 256)
_translators: list = []
_system_theme = "light"


def application() -> QApplication:
    """Возвращает приложение Qt (создаёт, если его ещё нет)."""
    app = QCoreApplication.instance()
    if app is None:
        app = QApplication([])
        _setup(app)
    return app


def _setup(app: QApplication) -> None:
    global _system_theme
    app.setStyle("Fusion")
    dark = app.styleHints().colorScheme() == Qt.ColorScheme.Dark
    _system_theme = "dark" if dark else "light"
    # Цвета рисуем сами по теме приложения, а настройка тёмного режима Windows
    # не должна красить стандартные части (меню, подсказки).
    app.styleHints().setColorScheme(Qt.ColorScheme.Light)
    QLocale.setDefault(QLocale(QLocale.Language.Russian))
    for name in ("qtbase", "qt"):
        translator = QTranslator(app)
        path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load(QLocale(QLocale.Language.Russian), name, "_", path):
            app.installTranslator(translator)
            _translators.append(translator)
    fonts.register_fonts()


def system_theme() -> str:
    """Тема операционной системы сейчас: ``light`` или ``dark``.

    В Windows читается настройка системы, поэтому смена темы замечается без
    перезапуска. На других системах берётся тема, найденная при запуске.
    """
    app = application()
    if sys.platform == "win32" and app.platformName() != "offscreen":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            with key:
                light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if light else "dark"
        except OSError:
            pass
    return _system_theme


def render_app_icon(size: int) -> QPixmap:
    """Рисует значок программы: фиолетовый скруглённый квадрат с белым крестом."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    begin(painter)
    fill_rounded(painter, pixmap.rect().toRectF(), size * 0.22, LIGHT.primary)
    glyph = round(size * 0.62)
    offset = round((size - glyph) / 2)
    painter.drawPixmap(offset, offset, icon_pixmap("cross", glyph, "#FFFFFF"))
    painter.end()
    return pixmap


def app_icon() -> QIcon:
    """Значок окна программы во всех размерах."""
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(render_app_icon(size))
    return icon


def screen_size(app: Optional[QApplication] = None) -> tuple:
    """Размер рабочей области основного экрана (ширина, высота)."""
    app = app or application()
    area = app.primaryScreen().availableGeometry()
    return area.width(), area.height()
