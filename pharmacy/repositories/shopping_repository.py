"""Запросы к таблице списка покупок."""

import sqlite3
from typing import List, Optional

from pharmacy.models import ShoppingItem
from pharmacy.repositories.base import BaseRepository


def _to_item(row: sqlite3.Row) -> ShoppingItem:
    """Превращает строку таблицы shopping_list в объект ShoppingItem."""
    return ShoppingItem(
        id=row["id"],
        user_id=row["user_id"],
        product_id=row["product_id"],
        name=row["name"],
        quantity=row["quantity"],
        unit=row["unit"],
        source=row["source"],
        is_bought=bool(row["is_bought"]),
        created_at=row["created_at"],
    )


class ShoppingRepository(BaseRepository):
    """Чтение и запись списка покупок. Каждый запрос ограничен пользователем."""

    def add(
        self,
        user_id: int,
        name: str,
        quantity: float,
        unit: str,
        source: str,
        product_id: Optional[int] = None,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Добавляет позицию в список покупок.

        Args:
            user_id: Владелец списка.
            name: Название позиции.
            quantity: Сколько купить (больше нуля).
            unit: Единица измерения.
            source: Откуда позиция (см. models.ShoppingSource).
            product_id: Товар аптечки, если позиция создана по нему.
            conn: Соединение внешней транзакции (необязательно).

        Returns:
            Идентификатор новой позиции.
        """
        return self._insert(
            "INSERT INTO shopping_list"
            " (user_id, product_id, name, quantity, unit, source)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, product_id, name, quantity, unit, source),
            conn,
        )

    def update_quantity(
        self,
        user_id: int,
        item_id: int,
        quantity: float,
        conn: Optional[sqlite3.Connection] = None,
    ) -> None:
        """Меняет, сколько нужно купить."""
        self._change(
            "UPDATE shopping_list SET quantity = ? WHERE id = ? AND user_id = ?",
            (quantity, item_id, user_id),
            conn,
        )

    def get(self, user_id: int, item_id: int) -> Optional[ShoppingItem]:
        """Находит позицию пользователя (None, если нет или она чужая)."""
        row = self.db.fetch_one(
            "SELECT * FROM shopping_list WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        )
        return _to_item(row) if row else None

    def find_open_for_product(
        self, user_id: int, product_id: int
    ) -> Optional[ShoppingItem]:
        """Находит ещё не купленную позицию, созданную по этому товару."""
        row = self.db.fetch_one(
            "SELECT * FROM shopping_list"
            " WHERE user_id = ? AND product_id = ? AND is_bought = 0",
            (user_id, product_id),
        )
        return _to_item(row) if row else None

    def list_for_user(
        self, user_id: int, is_bought: Optional[bool] = None
    ) -> List[ShoppingItem]:
        """Возвращает список покупок: сначала не купленные, новые выше.

        Args:
            user_id: Владелец списка.
            is_bought: Только купленные (True) или только нет (False);
                None возвращает все позиции.
        """
        sql = "SELECT * FROM shopping_list WHERE user_id = ?"
        params: list = [user_id]
        if is_bought is not None:
            sql += " AND is_bought = ?"
            params.append(int(is_bought))
        sql += " ORDER BY is_bought, created_at DESC, id DESC"
        return [_to_item(row) for row in self.db.fetch_all(sql, params)]

    def set_bought(
        self,
        user_id: int,
        item_id: int,
        is_bought: bool,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """Меняет отметку «куплено». Возвращает True, если позиция найдена."""
        return 0 < self._change(
            "UPDATE shopping_list SET is_bought = ? WHERE id = ? AND user_id = ?",
            (int(is_bought), item_id, user_id),
            conn,
        )

    def delete(
        self,
        user_id: int,
        item_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """Удаляет позицию. Возвращает True, если она найдена."""
        return 0 < self._change(
            "DELETE FROM shopping_list WHERE id = ? AND user_id = ?",
            (item_id, user_id),
            conn,
        )

    def delete_bought(self, user_id: int) -> int:
        """Удаляет все купленные позиции и возвращает их число."""
        return self._change(
            "DELETE FROM shopping_list WHERE user_id = ? AND is_bought = 1",
            (user_id,),
        )
