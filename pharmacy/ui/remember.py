"""Запоминание устройства: вход без пароля после перезапуска на 30 дней.

Пароль нигде не сохраняется. В файле лежат номер пользователя, срок действия
и отпечаток хэша пароля: при смене пароля запись перестаёт действовать.
"""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Union

REMEMBER_DAYS = 30
REMEMBER_FILE = "remember.json"  # лежит рядом с файлом базы


def fingerprint(password_hash: str) -> str:
    """Отпечаток хэша пароля, по которому запись узнаёт смену пароля."""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()


class RememberedLogin:
    """Одна запись «Запомнить это устройство». Без пути хранится только в памяти."""

    def __init__(self, path: Optional[Union[str, Path]] = None) -> None:
        self._path = Path(path) if path is not None else None
        self._data: dict = {}
        if self._path is not None and self._path.is_file():
            try:
                loaded = json.loads(self._path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                loaded = {}
            if isinstance(loaded, dict):
                self._data = loaded

    def remember(
        self, user_id: int, password_hash: str, now: Optional[datetime] = None
    ) -> None:
        """Запоминает пользователя на ``REMEMBER_DAYS`` дней."""
        now = now or datetime.now()
        self._data = {
            "user_id": user_id,
            "fingerprint": fingerprint(password_hash),
            "expires": (now + timedelta(days=REMEMBER_DAYS)).isoformat(),
        }
        self._save()

    def user_id(self, now: Optional[datetime] = None) -> Optional[int]:
        """Возвращает номер запомненного пользователя, если срок не истёк."""
        try:
            expires = datetime.fromisoformat(self._data["expires"])
            user_id = int(self._data["user_id"])
        except (KeyError, TypeError, ValueError):
            return None
        if (now or datetime.now()) >= expires:
            self.clear()
            return None
        return user_id

    def matches(self, password_hash: str) -> bool:
        """Проверяет, что пароль не менялся с момента запоминания."""
        return self._data.get("fingerprint") == fingerprint(password_hash)

    def clear(self) -> None:
        """Забывает устройство."""
        self._data = {}
        if self._path is not None:
            try:
                self._path.unlink()
            except OSError:
                pass

    def _save(self) -> None:
        if self._path is None:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._data), encoding="utf-8")
        except OSError:
            pass  # не записалось: вход попросят при следующем запуске
