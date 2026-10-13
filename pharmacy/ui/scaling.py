"""Автоматический масштаб интерфейса по разрешению и DPI экрана.

Qt сам учитывает масштаб системы (100%, 125%, 150%, 200%), но размеры макета
заданы в пикселях под экран 1920×1080. Поэтому коэффициент считается по размеру
экрана в логических пикселях (физическое разрешение, делённое на масштаб
системы) и применяется ко всему интерфейсу сразу: шрифтам, отступам, высоте
строк, ширине колонок, кнопкам и значкам.
"""

import os
import subprocess
import sys
from typing import Optional, Tuple

BASE_WIDTH = 1920  # экран, под который сделан макет
BASE_HEIGHT = 1080
MIN_SCALE = 0.75
MAX_SCALE = 1.5
STEP = 0.05
ENV_NAME = "QT_SCALE_FACTOR"
MIN_MANUAL = 0.8  # границы ручного масштаба в настройках
MAX_MANUAL = 1.5

_scale_factor = 1.0
_applied = False  # масштаб выбрала программа (а не QT_SCALE_FACTOR)
_auto = None
LOGIN_SCALE = 1.0  # вход и регистрация не мельче этого


def compute_scale_factor(width: int, height: int) -> float:
    """Считает коэффициент по размеру экрана в логических пикселях.

    Args:
        width: Ширина экрана с учётом масштаба системы.
        height: Высота экрана с учётом масштаба системы.

    Returns:
        Коэффициент от ``MIN_SCALE`` до ``MAX_SCALE`` с шагом ``STEP``.
    """
    raw = min(width / BASE_WIDTH, height / BASE_HEIGHT)
    clamped = max(MIN_SCALE, min(raw, MAX_SCALE))
    return round(round(clamped / STEP) * STEP, 2)


_PROBE = (
    "from PySide6.QtGui import QGuiApplication;"
    "a = QGuiApplication([]);"
    "g = a.primaryScreen().geometry();"
    "print(g.width(), g.height())"
)


def _screen_size() -> Optional[Tuple[int, int]]:
    """Определяет размер основного экрана в логических пикселях.

    Qt запоминает масштаб при первом запуске, поэтому экран опрашивает
    отдельный короткий процесс, а не временное приложение в этом же процессе.
    """
    if getattr(sys, "frozen", False):
        return _windows_screen_size()
    # Наш QT_SCALE_FACTOR не должен попасть в измерение: оно нужно «чистое».
    clean_env = {k: v for k, v in os.environ.items() if k != ENV_NAME}
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        env=clean_env,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    width, height = result.stdout.split()[-2:]
    return int(width), int(height)


def _windows_screen_size() -> Optional[Tuple[int, int]]:
    """Размер экрана в логических пикселях средствами Windows (для .exe)."""
    import ctypes

    user32 = ctypes.windll.user32
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    try:
        dpi = ctypes.windll.shcore.GetScaleFactorForDevice(0)  # 100, 125, 150...
    except (AttributeError, OSError):
        dpi = 100
    if width <= 0 or height <= 0:
        return None
    ratio = max(dpi, 100) / 100
    return round(width / ratio), round(height / ratio)


def auto_scale() -> float:
    """Масштаб, подобранный по экрану (1.0, если экран определить не удалось)."""
    global _auto
    if _auto is None:
        try:
            size = _screen_size()
        except Exception:
            size = None
        _auto = compute_scale_factor(*size) if size is not None else 1.0
    return _auto


def login_scale() -> float:
    """Масштаб входа и регистрации: по экрану, но не меньше обычного размера."""
    return max(auto_scale(), LOGIN_SCALE)


def session_scale(manual: Optional[float] = None) -> float:
    """Масштаб после входа: ручной из настроек или подобранный по экрану."""
    return clamp_manual(manual) if manual else auto_scale()


def clamp_manual(value: float) -> float:
    """Ручной масштаб в допустимых границах."""
    return round(max(MIN_MANUAL, min(value, MAX_MANUAL)), 2)


def apply_scale_factor(manual: Optional[float] = None, login: bool = False) -> float:
    """Определяет коэффициент и включает его до создания окна.

    На входе и регистрации (``login``) масштаб по экрану, но не меньше обычного.
    После входа берётся ручной масштаб из настроек, а если его нет, подобранный
    по экрану. Если задана переменная ``QT_SCALE_FACTOR``, берётся её значение.
    При ошибке определения экрана масштаб остаётся 1.0. Вызывать нужно до
    создания ``QApplication``.

    Args:
        manual: Коэффициент, выбранный пользователем (например, 1.25).
        login: Масштаб экранов входа и регистрации.

    Returns:
        Применённый коэффициент масштабирования.
    """
    global _scale_factor, _applied
    forced = os.environ.get(ENV_NAME)
    if forced:
        try:
            _scale_factor = float(forced)
        except ValueError:
            _scale_factor = 1.0
        return _scale_factor
    _applied = True
    _scale_factor = login_scale() if login else session_scale(manual)
    os.environ[ENV_NAME] = str(_scale_factor)
    return _scale_factor


def differs_from(target: float) -> bool:
    """Нужен ли перезапуск, чтобы масштаб стал ``target``.

    Если масштаб не выбирала сама программа (его задал ``QT_SCALE_FACTOR``
    или это тест), перезапуск не нужен.
    """
    return _applied and abs(_scale_factor - target) > 0.001


def scale_factor() -> float:
    """Возвращает коэффициент, применённый при запуске."""
    return _scale_factor
