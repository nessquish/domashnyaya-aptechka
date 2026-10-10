"""Запуск Qt: приложение, шрифты, русский язык стандартных окон и значок."""

import os
import subprocess
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

    Определяется по-разному в зависимости от окружения:

    * KDE Plasma — через ``kreadconfig5``/``kreadconfig6``;
    * Windows — через реестр;
    * остальные среды — через Qt ``QStyleHints``.

    Если ничего не удалось определить — возвращается значение,
    найденное при запуске.
    """
    # 1. KDE Plasma
    if os.environ.get("XDG_CURRENT_DESKTOP", "").upper().startswith("KDE"):
        for tool in ("kreadconfig6", "kreadconfig5"):
            try:
                result = subprocess.run(
                    [tool, "--file", "kdeglobals",
                     "--group", "General", "--key", "ColorScheme"],
                    capture_output=True, text=True, timeout=2,
                )
                name = (result.stdout or "").strip()
                if name:
                    return "dark" if "dark" in name.lower() else "light"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

    # 2. Windows
    if sys.platform == "win32":
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

    # 3. Qt (для GNOME и остальных сред)
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication

        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return "dark"
        if scheme == Qt.ColorScheme.Light:
            return "light"
    except (AttributeError, RuntimeError):
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
