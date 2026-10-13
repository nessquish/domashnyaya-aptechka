"""Запросы к таблице уведомлений."""

import sqlite3
from datetime import date
from typing import List, Optional

from pharmacy.models import Notification
from pharmacy.repositories.base import BaseRepository


def _to_notification(row: sqlite3.Row) -> Notification:
    """Превращает строку таблицы notifications в объект Notification."""
    return Notification(
        id=row["id"],
        user_id=row["user_id"],
        product_id=row["product_id"],
        kind=row["kind"],
        message=row["message"],
        is_read=bool(row["is_read"]),
        created_at=row["created_at"],
    )


class NotificationRepository(BaseRepository):
    """Чтение и запись уведомлений. Каждый запрос ограничен пользователем."""

    def add(
        self,
        user_id: int,
        product_id: int,
        kind: str,
        message: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Добавляет непрочитанное уведомление.

        Args:
            user_id: Получатель.
            product_id: Товар, о котором уведомление.
            kind: Вид уведомления (см. models.NotificationKind).
            message: Текст для пользователя.
            conn: Соединение внешней транзакции (необязательно).

        Returns:
            Идентификатор нового уведомления.
        """
        return self._insert(
            "INSERT INTO notifications (user_id, product_id, kind, message)"
            " VALUES (?, ?, ?, ?)",
            (user_id, product_id, kind, message),
            conn,
        )

    def get(self, user_id: int, notification_id: int) -> Optional[Notification]:
        """Находит уведомление пользователя (None, если нет или оно чужое)."""
        row = self.db.fetch_one(
            "SELECT * FROM notifications WHERE id = ? AND user_id = ?",
            (notification_id, user_id),
        )
        return _to_notification(row) if row else None

    def list_for_user(
        self,
        user_id: int,
        kind: Optional[str] = None,
        unread_only: bool = False,
        since: Optional[date] = None,
    ) -> List[Notification]:
        """Возвращает уведомления пользователя, самые новые первыми.

        Args:
            user_id: Получатель.
            kind: Только этого вида (необязательно).
            unread_only: Только непрочитанные.
            since: Только созданные не раньше этой даты (необязательно).

        Returns:
            Список уведомлений.
        """
        sql = "SELECT * FROM notifications WHERE user_id = ?"
        params: list = [user_id]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        if unread_only:
            sql += " AND is_read = 0"
        if since is not None:
            sql += " AND date(created_at) >= ?"
            params.append(since.isoformat())
        sql += " ORDER BY created_at DESC, id DESC"
        return [_to_notification(row) for row in self.db.fetch_all(sql, params)]

    def count_unread(self, user_id: int) -> int:
        """Считает непрочитанные уведомления пользователя."""
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS n FROM notifications"
            " WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )
        return row["n"]

    def update_message(
        self,
        notification_id: int,
        message: str,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        """Обновляет текст уведомления (например, при изменении количества)."""
        self._change(
            "UPDATE notifications SET message = ? WHERE id = ?",
            (message, notification_id),
            conn,
        )

    def mark_read(self, user_id: int, notification_id: int) -> bool:
        """Отмечает уведомление прочитанным. Возвращает True, если оно найдено."""
        return 0 < self._change(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (notification_id, user_id),
        )

    def mark_all_read(self, user_id: int) -> int:
        """Отмечает все уведомления пользователя прочитанными.

        Returns:
            Сколько уведомлений изменилось.
        """
        return self._change(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )

    def delete(
        self,
        user_id: int,
        notification_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """Удаляет уведомление пользователя. Возвращает True, если оно найдено."""
        return 0 < self._change(
            "DELETE FROM notifications WHERE id = ? AND user_id = ?",
            (notification_id, user_id),
            conn,
        )

    def delete_all(self, user_id: int) -> int:
        """Удаляет все уведомления пользователя и возвращает их число."""
        return self._change("DELETE FROM notifications WHERE user_id = ?", (user_id,))
