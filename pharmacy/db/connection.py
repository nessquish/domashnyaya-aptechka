"""Менеджер базы данных SQLite (паттерн Database Manager из ТЗ).

Все остальные модули обращаются к базе только через класс ``Database``.
Значения в запросы всегда передаются параметрами (``?``), а не вставляются
в текст запроса: это защита от SQL-инъекций.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Sequence, Union

from pharmacy.config import get_db_path
from pharmacy.db.schema import DEFAULT_CATEGORIES, SCHEMA_SQL, SHOPPING_SOURCES


def _casefold(value: object) -> object:
    """Приводит строку к нижнему регистру для сравнения (работает и с кириллицей).

    Встроенные LIKE и NOCASE в SQLite не различают регистр только у латиницы,
    поэтому поиск по русским названиям делается через эту функцию.
    """
    return value.casefold() if isinstance(value, str) else value


class Database:
    """Подключение к файлу SQLite и выполнение запросов.

    Каждая операция открывает короткое соединение и закрывает его после
    завершения, поэтому файл базы не остаётся заблокированным.

    Attributes:
        path: Путь к файлу базы данных.
    """

    def __init__(self, path: Optional[Union[str, Path]] = None) -> None:
        """Создаёт менеджер базы.

        Args:
            path: Путь к файлу базы. Если не указан, берётся путь из настроек.
        """
        self.path = Path(path) if path is not None else get_db_path()

    def _open(self) -> sqlite3.Connection:
        """Открывает соединение: строки как словари, внешние ключи включены."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        # В SQLite внешние ключи по умолчанию выключены, а без них не работают
        # каскадное удаление и проверки связей между таблицами.
        conn.execute("PRAGMA foreign_keys = ON")
        conn.create_function("casefold", 1, _casefold, deterministic=True)
        return conn

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Транзакция: либо сохраняются все изменения, либо ни одно.

        Yields:
            Открытое соединение для выполнения нескольких запросов подряд.

        Raises:
            Exception: Любая ошибка внутри блока; изменения при этом откатываются.
        """
        conn = self._open()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        """Создаёт таблицы и индексы, если их ещё нет, и заполняет категории."""
        with self.transaction() as conn:
            self._migrate_shopping_sources(conn)
            conn.executescript(SCHEMA_SQL)
            conn.executemany(
                "INSERT OR IGNORE INTO categories (name) VALUES (?)",
                [(name,) for name in DEFAULT_CATEGORIES],
            )

    @staticmethod
    def _migrate_shopping_sources(conn: sqlite3.Connection) -> None:
        """Переносит старую таблицу покупок: в ней источник мог быть только двух видов.

        SQLite не умеет менять ограничение CHECK, поэтому таблица создаётся заново
        с тем же содержимым. Новые базы и уже перенесённые эту работу пропускают.
        """
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table'"
            " AND name = 'shopping_list'"
        ).fetchone()
        if row is None or all(f"'{name}'" in row["sql"] for name in SHOPPING_SOURCES):
            return
        conn.execute("ALTER TABLE shopping_list RENAME TO shopping_list_old")
        conn.execute("DROP INDEX IF EXISTS idx_shopping_user_bought")
        start = SCHEMA_SQL.index("CREATE TABLE IF NOT EXISTS shopping_list")
        end = SCHEMA_SQL.index(";", start)
        conn.execute(SCHEMA_SQL[start:end])
        conn.execute(
            "INSERT INTO shopping_list (id, user_id, product_id, name, quantity,"
            " unit, source, is_bought, created_at)"
            " SELECT id, user_id, product_id, name, quantity, unit, source,"
            " is_bought, created_at FROM shopping_list_old"
        )
        conn.execute("DROP TABLE shopping_list_old")

    def fetch_all(self, sql: str, params: Sequence = ()) -> list[sqlite3.Row]:
        """Выполняет SELECT и возвращает все строки.

        Args:
            sql: Текст запроса с метками ``?`` вместо значений.
            params: Значения для меток.

        Returns:
            Список строк (к полям можно обращаться по имени).
        """
        with self.transaction() as conn:
            return conn.execute(sql, params).fetchall()

    def fetch_one(self, sql: str, params: Sequence = ()) -> Optional[sqlite3.Row]:
        """Выполняет SELECT и возвращает первую строку.

        Args:
            sql: Текст запроса с метками ``?`` вместо значений.
            params: Значения для меток.

        Returns:
            Первая найденная строка или None, если ничего не найдено.
        """
        with self.transaction() as conn:
            return conn.execute(sql, params).fetchone()

    def execute(self, sql: str, params: Sequence = ()) -> int:
        """Выполняет INSERT, UPDATE или DELETE.

        Args:
            sql: Текст запроса с метками ``?`` вместо значений.
            params: Значения для меток.

        Returns:
            Идентификатор добавленной записи (для INSERT).

        Raises:
            sqlite3.IntegrityError: Если нарушено ограничение базы
                (уникальность, CHECK, внешний ключ).
        """
        with self.transaction() as conn:
            return conn.execute(sql, params).lastrowid
