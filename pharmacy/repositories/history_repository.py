"""Запросы к таблице истории действий."""

import sqlite3
from datetime import date
from typing import List, Optional

from pharmacy.models import HistoryRecord
from pharmacy.repositories.base import BaseRepository


def _to_record(row: sqlite3.Row) -> HistoryRecord:
    """Превращает строку таблицы history в объект HistoryRecord."""
    return HistoryRecord(
        id=row["id"],
        user_id=row["user_id"],
        product_id=row["product_id"],
        action=row["action"],
        description=row["description"],
        created_at=row["created_at"],
    )


class HistoryRepository(BaseRepository):
    """Запись и чтение истории действий."""

    def add(
        self,
        user_id: int,
        product_id: Optional[int],
        action: str,
        description: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Добавляет запись в историю.

        Args:
            user_id: Пользователь, выполнивший действие.
            product_id: Товар или None (например, если товар удалён).
            action: Код действия (см. models.HistoryAction).
            description: Описание для показа пользователю.
            conn: Соединение внешней транзакции (необязательно).

        Returns:
            Идентификатор новой записи.
        """
        return self._insert(
            "INSERT INTO history (user_id, product_id, action, description)"
            " VALUES (?, ?, ?, ?)",
            (user_id, product_id, action, description),
            conn,
        )

    def list_for_user(
        self,
        user_id: int,
        action: Optional[str] = None,
        limit: Optional[int] = None,
        since: Optional[date] = None,
    ) -> List[HistoryRecord]:
        """Возвращает историю пользователя, самые новые записи первыми.

        Args:
            user_id: Идентификатор пользователя.
            action: Показать только действия этого вида (необязательно).
            limit: Сколько записей вернуть не больше (необязательно).
            since: Только записи не раньше этой даты (необязательно).

        Returns:
            Список записей.
        """
        sql = "SELECT * FROM history WHERE user_id = ?"
        params: list = [user_id]
        if action is not None:
            sql += " AND action = ?"
            params.append(action)
        if since is not None:
            sql += " AND date(created_at) >= ?"
            params.append(since.isoformat())
        sql += " ORDER BY created_at DESC, id DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        return [_to_record(row) for row in self.db.fetch_all(sql, params)]

    def delete_all(self, user_id: int) -> int:
        """Очищает историю пользователя и возвращает число удалённых записей."""
        return self._change("DELETE FROM history WHERE user_id = ?", (user_id,))
