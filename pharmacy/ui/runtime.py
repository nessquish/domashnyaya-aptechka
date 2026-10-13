"""Запуск Qt: приложение, шрифты, русский язык стандартных окон и значок."""

import os
import subprocess
import sys
from typing import Optional

from PySide6.QtCore import (
    QCoreApplication,
    QLibraryInfo,
    QLocale,
    QProcess,
    QTranslator,
    Qt,
)
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from pharmacy.ui import fonts, scaling
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


def _kde_theme() -> Optional[str]:
    """Тема KDE Plasma через ``kreadconfig`` (None, если это не KDE)."""
    if not os.environ.get("XDG_CURRENT_DESKTOP", "").upper().startswith("KDE"):
        return None
    for tool in ("kreadconfig6", "kreadconfig5"):
        command = [tool, "--file", "kdeglobals", "--group", "General"]
        try:
            result = subprocess.run(
                command + ["--key", "ColorScheme"],
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        name = (result.stdout or "").strip()
        if name:
            return "dark" if "dark" in name.lower() else "light"
    return None


def _windows_theme() -> Optional[str]:
    """Тема Windows из реестра (None, если это не Windows или ключа нет)."""
    if sys.platform != "win32":
        return None
    import winreg

    path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except OSError:
        return None
    return "light" if light else "dark"


def _qt_theme() -> Optional[str]:
    """Тема по данным Qt (для GNOME и остальных сред)."""
    try:
        scheme = QGuiApplication.styleHints().colorScheme()
    except (AttributeError, RuntimeError):
        return None
    if scheme == Qt.ColorScheme.Dark:
        return "dark"
    return "light" if scheme == Qt.ColorScheme.Light else None


def restart_program() -> None:
    """Запускает программу заново (масштаб считается заново) и закрывает эту."""
    os.environ.pop(scaling.ENV_NAME, None)
    args = [] if getattr(sys, "frozen", False) else ["-m", "pharmacy"]
    QProcess.startDetached(sys.executable, args)
    QApplication.quit()


def system_theme() -> str:
    """Тема операционной системы сейчас: ``light`` или ``dark``.

    Сначала пробуем KDE, затем реестр Windows, затем Qt. Если ничего не
    удалось определить, возвращается тема, найденная при запуске.
    """
    for detect in (_kde_theme, _windows_theme, _qt_theme):
        found = detect()
        if found:
            return found
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
