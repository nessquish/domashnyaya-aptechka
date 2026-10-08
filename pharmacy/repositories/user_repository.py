"""Запросы к таблице пользователей."""

import sqlite3
from typing import Optional

from pharmacy.models import User
from pharmacy.repositories.base import BaseRepository


def _to_user(row: sqlite3.Row) -> User:
    """Превращает строку таблицы users в объект User."""
    return User(
        id=row["id"],
        login=row["login"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        warning_days=row["warning_days"],
        theme=row["theme"],
        notify_expired=bool(row["notify_expired"]),
        notify_low_stock=bool(row["notify_low_stock"]),
        created_at=row["created_at"],
    )


class UserRepository(BaseRepository):
    """Чтение и запись пользователей."""

    def add(
        self,
        login: str,
        username: str,
        email: str,
        password_hash: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Добавляет пользователя.

        Args:
            login: Логин.
            username: Имя пользователя.
            email: Электронная почта.
            password_hash: Хэш пароля.
            conn: Соединение внешней транзакции (необязательно).

        Returns:
            Идентификатор нового пользователя.

        Raises:
            sqlite3.IntegrityError: Если логин или почта уже заняты.
        """
        with self._connection(conn) as c:
            cursor = c.execute(
                "INSERT INTO users (login, username, email, password_hash)"
                " VALUES (?, ?, ?, ?)",
                (login, username, email, password_hash),
            )
            return cursor.lastrowid

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Находит пользователя по идентификатору (None, если нет)."""
        row = self.db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        return _to_user(row) if row else None

    def get_by_login(self, login: str) -> Optional[User]:
        """Находит пользователя по логину без учёта регистра букв.

        Args:
            login: Логин.

        Returns:
            Пользователь или None, если такого логина нет.
        """
        row = self.db.fetch_one(
            "SELECT * FROM users WHERE login = ? COLLATE NOCASE", (login,)
        )
        return _to_user(row) if row else None

    def get_by_email(self, email: str) -> Optional[User]:
        """Находит пользователя по почте без учёта регистра букв.

        Args:
            email: Электронная почта.

        Returns:
            Пользователь или None, если такой почты нет.
        """
        row = self.db.fetch_one(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)
        )
        return _to_user(row) if row else None

    def email_exists(self, email: str) -> bool:
        """Проверяет, зарегистрирована ли уже такая почта (без учёта регистра)."""
        row = self.db.fetch_one(
            "SELECT 1 AS found FROM users WHERE email = ? COLLATE NOCASE", (email,)
        )
        return row is not None

    def email_used_by_other(self, email: str, user_id: int) -> bool:
        """Проверяет, занята ли почта другим пользователем (не user_id)."""
        row = self.db.fetch_one(
            "SELECT 1 AS found FROM users"
            " WHERE email = ? COLLATE NOCASE AND id != ?",
            (email, user_id),
        )
        return row is not None

    def update_profile(
        self, user_id: int, username: str, email: str, login: Optional[str] = None
    ) -> None:
        """Меняет имя, почту и (если указан) логин пользователя."""
        with self._connection() as c:
            if login is None:
                c.execute(
                    "UPDATE users SET username = ?, email = ? WHERE id = ?",
                    (username, email, user_id),
                )
            else:
                c.execute(
                    "UPDATE users SET username = ?, email = ?, login = ?"
                    " WHERE id = ?",
                    (username, email, login, user_id),
                )

    def update_settings(
        self,
        user_id: int,
        warning_days: int,
        theme: str,
        notify_expired: bool,
        notify_low_stock: bool,
    ) -> None:
        """Сохраняет настройки пользователя."""
        with self._connection() as c:
            c.execute(
                "UPDATE users SET warning_days = ?, theme = ?,"
                " notify_expired = ?, notify_low_stock = ? WHERE id = ?",
                (
                    warning_days,
                    theme,
                    int(notify_expired),
                    int(notify_low_stock),
                    user_id,
                ),
            )

    def update_password_hash(
        self,
        user_id: int,
        password_hash: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        """Заменяет хэш пароля пользователя.

        Args:
            user_id: Идентификатор пользователя.
            password_hash: Новый хэш пароля.
            conn: Соединение внешней транзакции (необязательно).
        """
        with self._connection(conn) as c:
            c.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id),
            )

    def delete(self, user_id: int) -> None:
        """Удаляет пользователя; товары, покупки и история удаляются каскадом."""
        with self._connection(None) as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
