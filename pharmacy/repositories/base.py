"""Общая основа репозиториев."""

import sqlite3
from contextlib import contextmanager
from typing import Iterator, Optional

from pharmacy.db.connection import Database


class BaseRepository:
    """Хранит менеджер базы и умеет работать внутри чужой транзакции.

    Если сервису нужно выполнить несколько операций как одну (например,
    добавить товар и записать это в историю), он открывает транзакцию сам
    и передаёт соединение в методы репозиториев параметром ``conn``.
    """

    def __init__(self, db: Database) -> None:
        """Запоминает менеджер базы данных.

        Args:
            db: Менеджер базы данных.
        """
        self.db = db

    @contextmanager
    def _connection(
        self, conn: Optional[sqlite3.Connection] = None
    ) -> Iterator[sqlite3.Connection]:
        """Даёт соединение: переданное или новое (в отдельной транзакции).

        Args:
            conn: Соединение внешней транзакции или None.

        Yields:
            Соединение для выполнения запросов.
        """
        if conn is not None:
            yield conn
        else:
            with self.db.transaction() as own:
                yield own

    def _insert(self, sql: str, params: tuple, conn=None) -> int:
        """Выполняет вставку и возвращает идентификатор новой строки."""
        with self._connection(conn) as c:
            return c.execute(sql, params).lastrowid

    def _change(self, sql: str, params: tuple, conn=None) -> int:
        """Выполняет изменение или удаление и возвращает число затронутых строк."""
        with self._connection(conn) as c:
            return c.execute(sql, params).rowcount
