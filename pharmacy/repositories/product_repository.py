"""Запросы к таблице товаров.

Каждый запрос ограничен идентификатором пользователя: товары одного
пользователя никогда не видны другому.
"""

import sqlite3
from datetime import date
from typing import List, Optional

from pharmacy.models import Product, ProductData
from pharmacy.repositories.base import BaseRepository

# Варианты сортировки. Текст для ORDER BY берётся только отсюда, а не из ввода
# пользователя: так в запрос не может попасть чужой SQL.
SORT_ORDERS = {
    "name": "casefold(p.name), p.id",
    "name_desc": "casefold(p.name) DESC, p.id",
    # Товары без срока годности всегда в конце, в какую сторону ни сортируй.
    "expiry": "p.expiry_date IS NULL, p.expiry_date, casefold(p.name)",
    "expiry_desc": "p.expiry_date IS NULL, p.expiry_date DESC, casefold(p.name)",
    "quantity": "p.quantity, casefold(p.name)",
    "quantity_desc": "p.quantity DESC, casefold(p.name)",
    "added": "p.created_at DESC, p.id DESC",
    "added_asc": "p.created_at, p.id",
    "category": "casefold(c.name), casefold(p.name)",
    "category_desc": "casefold(c.name) DESC, casefold(p.name)",
    # Товары без места хранения всегда в конце.
    "place": (
        "COALESCE(p.storage_place, '') = '', casefold(p.storage_place),"
        " casefold(p.name)"
    ),
    "place_desc": (
        "COALESCE(p.storage_place, '') = '', casefold(p.storage_place) DESC,"
        " casefold(p.name)"
    ),
}

_SELECT = (
    "SELECT p.*, c.name AS category_name FROM products p"
    " JOIN categories c ON c.id = p.category_id"
)


def _to_product(row: sqlite3.Row) -> Product:
    """Превращает строку запроса в объект Product."""
    expiry = row["expiry_date"]
    return Product(
        id=row["id"],
        user_id=row["user_id"],
        category_id=row["category_id"],
        category_name=row["category_name"],
        name=row["name"],
        quantity=row["quantity"],
        unit=row["unit"],
        expiry_date=date.fromisoformat(expiry) if expiry else None,
        indications=row["indications"] or "",
        storage_place=row["storage_place"] or "",
        min_quantity=row["min_quantity"],
        note=row["note"] or "",
        created_at=row["created_at"],
    )


def _escape_like(text: str) -> str:
    """Экранирует символы %, _ и \\, чтобы поиск воспринимал их как обычные."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _values(data: ProductData) -> tuple:
    """Значения полей товара в порядке, который используют запросы."""
    return (
        data.category_id,
        data.name,
        data.quantity,
        data.unit,
        data.expiry_date.isoformat() if data.expiry_date else None,
        data.indications,
        data.storage_place,
        data.min_quantity,
        data.note,
    )


class ProductRepository(BaseRepository):
    """Создание, чтение, изменение и удаление товаров."""

    def add(
        self,
        user_id: int,
        data: ProductData,
        conn: Optional[sqlite3.Connection] = None,
    ) -> int:
        """Добавляет товар пользователю.

        Args:
            user_id: Владелец товара.
            data: Проверенные данные товара.
            conn: Соединение внешней транзакции (необязательно).

        Returns:
            Идентификатор нового товара.
        """
        return self._insert(
            "INSERT INTO products (user_id, category_id, name, quantity, unit,"
            " expiry_date, indications, storage_place, min_quantity, note)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id,) + _values(data),
            conn,
        )

    def get(self, user_id: int, product_id: int) -> Optional[Product]:
        """Находит товар пользователя по идентификатору.

        Args:
            user_id: Владелец товара.
            product_id: Идентификатор товара.

        Returns:
            Товар или None, если его нет или он принадлежит другому пользователю.
        """
        row = self.db.fetch_one(
            _SELECT + " WHERE p.id = ? AND p.user_id = ?", (product_id, user_id)
        )
        return _to_product(row) if row else None

    def list_for_user(
        self,
        user_id: int,
        search: str = "",
        category_id: Optional[int] = None,
        sort: str = "name",
    ) -> List[Product]:
        """Возвращает товары пользователя с поиском, фильтром и сортировкой.

        Args:
            user_id: Владелец товаров.
            search: Часть названия (регистр букв не важен, в том числе у русских).
            category_id: Показать только эту категорию (необязательно).
            sort: Вид сортировки: ``name``, ``expiry``, ``quantity`` или ``added``.

        Returns:
            Список товаров.

        Raises:
            ValueError: Если вид сортировки неизвестен.
        """
        order = SORT_ORDERS.get(sort)
        if order is None:
            raise ValueError(f"Неизвестный вид сортировки: {sort}")
        sql = _SELECT + " WHERE p.user_id = ?"
        params: list = [user_id]
        search = search.strip()
        if search:
            sql += " AND casefold(p.name) LIKE ? ESCAPE '\\'"
            params.append(f"%{_escape_like(search.casefold())}%")
        if category_id is not None:
            sql += " AND p.category_id = ?"
            params.append(category_id)
        sql += f" ORDER BY {order}"  # order взят из SORT_ORDERS, не из ввода
        return [_to_product(row) for row in self.db.fetch_all(sql, params)]

    def update(
        self,
        user_id: int,
        product_id: int,
        data: ProductData,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """Обновляет товар пользователя.

        Args:
            user_id: Владелец товара.
            product_id: Идентификатор товара.
            data: Новые данные товара.
            conn: Соединение внешней транзакции (необязательно).

        Returns:
            True, если товар найден и обновлён.
        """
        return 0 < self._change(
            "UPDATE products SET category_id = ?, name = ?, quantity = ?,"
            " unit = ?, expiry_date = ?, indications = ?, storage_place = ?,"
            " min_quantity = ?, note = ? WHERE id = ? AND user_id = ?",
            _values(data) + (product_id, user_id),
            conn,
        )

    def delete(
        self,
        user_id: int,
        product_id: int,
        conn: Optional[sqlite3.Connection] = None,
    ) -> bool:
        """Удаляет товар пользователя.

        Args:
            user_id: Владелец товара.
            product_id: Идентификатор товара.
            conn: Соединение внешней транзакции (необязательно).

        Returns:
            True, если товар найден и удалён.
        """
        return 0 < self._change(
            "DELETE FROM products WHERE id = ? AND user_id = ?",
            (product_id, user_id),
            conn,
        )
