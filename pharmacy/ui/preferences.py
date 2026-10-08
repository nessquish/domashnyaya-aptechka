"""Предпочтения отображения: размер текста и состояние боковой панели.

Это настройки внешнего вида, а не данные аптечки, поэтому они хранятся
отдельным JSON-файлом рядом с базой (схема базы остаётся по ER-диаграмме).
Предпочтения свои у каждого пользователя.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

GLOBAL_USER = 0  # предпочтения, общие для всех пользователей (масштаб окна)
SCALE_MODE = "scale_mode"  # auto или manual
SCALE_PERCENT = "scale_percent"  # от 80 до 150
MENU_ICONS = "menu_icons"  # показывать значки в боковом меню


class Preferences:
    """Чтение и запись предпочтений пользователей.

    Если путь не задан, предпочтения хранятся только в памяти (тесты и
    запуск без файла). Повреждённый файл не мешает запуску: берутся
    значения по умолчанию.
    """

    def __init__(self, path: Optional[Union[str, Path]] = None) -> None:
        """Загружает предпочтения из файла, если он есть.

        Args:
            path: Путь к JSON-файлу или None для хранения в памяти.
        """
        self._path = Path(path) if path is not None else None
        self._data: Dict[str, Dict[str, Any]] = {}
        if self._path is not None and self._path.is_file():
            self._load()

    def _load(self) -> None:
        try:
            loaded = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(loaded, dict):
            self._data = {
                str(user): values
                for user, values in loaded.items()
                if isinstance(values, dict)
            }

    def get(self, user_id: int, key: str, default: Any = None) -> Any:
        """Возвращает предпочтение пользователя или значение по умолчанию."""
        return self._data.get(str(user_id), {}).get(key, default)

    def set(self, user_id: int, key: str, value: Any) -> None:
        """Запоминает предпочтение и сразу сохраняет файл."""
        self._data.setdefault(str(user_id), {})[key] = value
        self._save()

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass  # не удалось записать: настройка действует до закрытия программы
