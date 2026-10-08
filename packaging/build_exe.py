"""Сборка программы в один файл Aptechka.exe.

Запуск из папки проекта::

    .venv\\Scripts\\python.exe packaging\\build_exe.py

Результат: ``dist/Aptechka.exe``. С ключом ``--demo`` собирается
``dist/Aptechka-Demo.exe``: при первом запуске в нём уже есть тестовый аккаунт
``nessquish`` (пароль ``demo12345``) со всеми видами данных, а данные лежат
отдельно в ``%LOCALAPPDATA%\\Моя аптечка (демо)``.

Обычная сборка: Файл можно скопировать на другой компьютер с
Windows: Python на нём не нужен. Данные программы (база и настройки) хранятся
в ``%LOCALAPPDATA%\\Моя аптечка`` и сохраняются между запусками.
"""

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import PyInstaller.__main__  # noqa: E402
from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QIODevice  # noqa: E402

from pharmacy.ui import runtime  # noqa: E402

BUILD_DIR = ROOT / "build"
ICON_FILE = BUILD_DIR / "aptechka.ico"
ENTRY = ROOT / "packaging" / "launcher.py"
FONTS = ROOT / "pharmacy" / "ui" / "assets" / "fonts"
EXE_NAME = "Aptechka"
DEMO_FLAG_FILE = BUILD_DIR / "demo.flag"


def make_icon() -> Path:
    """Рисует значок и сохраняет его как .ico со всеми размерами."""
    runtime.application()
    BUILD_DIR.mkdir(exist_ok=True)
    pixmap = runtime.render_app_icon(max(runtime.ICON_SIZES))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    biggest = Image.open(io.BytesIO(bytes(buffer.data())))
    biggest.save(ICON_FILE, sizes=[(size, size) for size in runtime.ICON_SIZES])
    return ICON_FILE


def build(demo: bool = False) -> None:
    """Запускает PyInstaller (demo: сборка с тестовым аккаунтом)."""
    icon = make_icon()
    extra = []
    if demo:
        DEMO_FLAG_FILE.write_text("demo", encoding="utf-8")
        extra = ["--add-data", f"{DEMO_FLAG_FILE};pharmacy"]
    PyInstaller.__main__.run(
        [
            str(ENTRY),
            *extra,
            "--name",
            EXE_NAME + ("-Demo" if demo else ""),
            "--onefile",
            "--noconsole",
            "--clean",
            "--noconfirm",
            "--icon",
            str(icon),
            # Интерфейс на Qt, поэтому Tkinter в программу не нужен.
            "--exclude-module",
            "tkinter",
            # Шрифт Inter читается из файлов, поэтому кладём их внутрь программы.
            "--add-data",
            f"{FONTS};pharmacy/ui/assets/fonts",
            "--paths",
            str(ROOT),
            "--distpath",
            str(ROOT / "dist"),
            "--workpath",
            str(BUILD_DIR / "work"),
            "--specpath",
            str(BUILD_DIR),
        ]
    )


if __name__ == "__main__":
    build(demo="--demo" in sys.argv)
