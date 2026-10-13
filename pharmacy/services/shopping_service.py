"""Список покупок: ручное добавление, добавление по товару, отметка «куплено»."""

from typing import List, Optional, Sequence, Tuple

from pharmacy.db.connection import Database
from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.models import HistoryAction, ShoppingItem, ShoppingSource
from pharmacy.repositories.history_repository import HistoryRepository
from pharmacy.repositories.product_repository import ProductRepository
from pharmacy.repositories.shopping_repository import ShoppingRepository
from pharmacy.services.product_service import (
    MAX_NAME_LENGTH,
    _check_length,
    _parse_amount,
)
from pharmacy.utils.formatting import format_quantity
from pharmacy.utils.textmatch import find_matching
from pharmacy.utils.units import DEFAULT_UNIT, normalize_unit


def _describe(item: ShoppingItem) -> str:
    """Название с количеством для записи в историю."""
    return f"{item.name} · {format_quantity(item.quantity)} {item.unit}"


class ShoppingService:
    """Правила работы со списком покупок. Действия попадают в историю."""

    def __init__(self, db: Database) -> None:
        """Создаёт сервис.

        Args:
            db: Менеджер базы данных.
        """
        self._db = db
        self._items = ShoppingRepository(db)
        self._products = ProductRepository(db)
        self._history = HistoryRepository(db)

    def add_manual(
        self,
        user_id: int,
        name: str,
        quantity: str = "1",
        unit: str = DEFAULT_UNIT,
        product_id: Optional[int] = None,
    ) -> ShoppingItem:
        """Добавляет в список покупок позицию, введённую вручную.

        Args:
            user_id: Владелец списка.
            name: Название (обязательно).
            quantity: Количество текстом, больше нуля (по умолчанию 1).
            unit: Единица измерения (по умолчанию «шт.»).
            product_id: Товар аптечки, выбранный в подсказках при вводе названия:
                по нему у позиции появляется ссылка на карточку.

        Returns:
            Добавленная позиция.

        Raises:
            NotFoundError: Если выбранного товара нет или он чужой.
            ValidationError: Если название пустое или количество неверно.
        """
        name = _check_length(name, MAX_NAME_LENGTH, "Название", "name")
        if not name:
            raise ValidationError("Введите название", "name")
        amount = _parse_amount(quantity or "1", "quantity", None)
        if amount <= 0:
            raise ValidationError("Количество должно быть больше нуля", "quantity")
        unit = normalize_unit(unit)
        if product_id is not None:
            if self._products.get(user_id, product_id) is None:
                raise NotFoundError("Товар не найден")
            existing = self._items.find_open_for_product(user_id, product_id)
            if existing is not None:
                return self._increase(user_id, existing, amount)
        return self._add(user_id, name, amount, unit, ShoppingSource.MANUAL, product_id)

    def add_from_product(
        self,
        user_id: int,
        product_id: int,
        quantity: Optional[str] = None,
        source: str = ShoppingSource.NOTIFICATION,
    ) -> ShoppingItem:
        """Добавляет в список покупок товар из аптечки.

        Количество в списке покупок свой, не связан с остатком в аптечке.
        Если количество не указано, добавляется одна единица (из уведомления
        предлагается докупить до двойного минимального остатка, но не меньше
        одной). Если товар уже есть в списке и не куплен, его количество
        увеличивается на столько же, а не создаётся вторая позиция.

        Args:
            user_id: Владелец списка.
            product_id: Товар аптечки.
            quantity: Сколько добавить, текстом (необязательно).
            source: Откуда добавлено (см. models.ShoppingSource).

        Returns:
            Позиция списка покупок (новая или с увеличенным количеством).

        Raises:
            NotFoundError: Если товара нет или он чужой.
            ValidationError: Если количество неверно.
        """
        product = self._products.get(user_id, product_id)
        if product is None:
            raise NotFoundError("Товар не найден")
        if quantity:
            amount = _parse_amount(quantity, "quantity", None)
            if amount <= 0:
                raise ValidationError("Количество должно быть больше нуля", "quantity")
        elif source == ShoppingSource.NOTIFICATION:
            amount = max(product.min_quantity * 2 - product.quantity, 1)
        else:
            amount = 1.0
        existing = self._items.find_open_for_product(user_id, product_id)
        if existing is not None:
            return self._increase(user_id, existing, amount)
        return self._add(
            user_id,
            product.name,
            amount,
            product.unit or DEFAULT_UNIT,
            source,
            product.id,
        )

    def add_products(
        self,
        user_id: int,
        product_ids: Sequence[int],
        source: str = ShoppingSource.KIT,
    ) -> Tuple[int, int]:
        """Добавляет в список покупок несколько товаров аптечки.

        Каждый товар добавляется на одну единицу; если он уже в списке, его
        количество увеличивается. Недоступные товары пропускаются.

        Returns:
            Пара: сколько позиций создано и у скольких увеличено количество.
        """
        created = increased = 0
        for product_id in product_ids:
            was_in_list = self.is_in_list(user_id, product_id)
            try:
                self.add_from_product(user_id, product_id, source=source)
            except (NotFoundError, ValidationError):
                continue
            increased += was_in_list
            created += not was_in_list
        return created, increased

    def _increase(
        self, user_id: int, item: ShoppingItem, amount: float
    ) -> ShoppingItem:
        """Увеличивает количество у позиции, которая уже есть в списке."""
        total = item.quantity + amount
        with self._db.transaction() as conn:
            self._items.update_quantity(user_id, item.id, total, conn)
            self._history.add(
                user_id,
                item.product_id,
                HistoryAction.SHOPPING_ADDED,
                f"{item.name} · +{format_quantity(amount)} {item.unit} · "
                f"в списке покупок теперь {format_quantity(total)} {item.unit}",
                conn,
            )
        return self._require(user_id, item.id)

    def search_items(
        self, user_id: int, query: str, limit: int = 10
    ) -> List[ShoppingItem]:
        """Ищет позиции списка покупок по названию (для поиска по программе)."""
        items = self._items.list_for_user(user_id)
        return find_matching(items, lambda item: item.name, query, limit)

    def is_in_list(self, user_id: int, product_id: int) -> bool:
        """Проверяет, есть ли товар в списке покупок среди не купленных."""
        return self._items.find_open_for_product(user_id, product_id) is not None

    def list_items(
        self, user_id: int, is_bought: Optional[bool] = None
    ) -> List[ShoppingItem]:
        """Возвращает список покупок (не купленные сверху)."""
        return self._items.list_for_user(user_id, is_bought)

    def set_bought(
        self, user_id: int, item_id: int, is_bought: bool = True
    ) -> ShoppingItem:
        """Отмечает позицию купленной (или снимает отметку).

        Покупка записывается в историю. Остаток товара аптечки не меняется:
        пользователь сам вносит купленное через форму товара.

        Raises:
            NotFoundError: Если позиции нет или она чужая.
        """
        item = self._require(user_id, item_id)
        if item.is_bought == is_bought:
            return item
        with self._db.transaction() as conn:
            self._items.set_bought(user_id, item_id, is_bought, conn)
            if is_bought:
                self._history.add(
                    user_id,
                    item.product_id,
                    HistoryAction.SHOPPING_BOUGHT,
                    f"{_describe(item)} · куплено",
                    conn,
                )
        return self._require(user_id, item_id)

    def remove(self, user_id: int, item_id: int) -> None:
        """Удаляет позицию из списка и записывает это в историю.

        Raises:
            NotFoundError: Если позиции нет или она чужая.
        """
        item = self._require(user_id, item_id)
        with self._db.transaction() as conn:
            self._items.delete(user_id, item_id, conn)
            self._history.add(
                user_id,
                item.product_id,
                HistoryAction.SHOPPING_REMOVED,
                f"{item.name} · удалено из списка покупок",
                conn,
            )

    def clear_bought(self, user_id: int) -> int:
        """Убирает из списка все купленные позиции и возвращает их число."""
        return self._items.delete_bought(user_id)

    def _add(
        self,
        user_id: int,
        name: str,
        quantity: float,
        unit: str,
        source: str,
        product_id: Optional[int],
    ) -> ShoppingItem:
        """Добавляет позицию и запись в историю одной транзакцией."""
        with self._db.transaction() as conn:
            item_id = self._items.add(
                user_id, name, quantity, unit, source, product_id, conn
            )
            self._history.add(
                user_id,
                product_id,
                HistoryAction.SHOPPING_ADDED,
                f"{name} · {format_quantity(quantity)} {unit} · "
                "добавлено в список покупок",
                conn,
            )
        return self._require(user_id, item_id)

    def _require(self, user_id: int, item_id: int) -> ShoppingItem:
        """Возвращает позицию или бросает NotFoundError."""
        item = self._items.get(user_id, item_id)
        if item is None:
            raise NotFoundError("Позиция не найдена")
        return item
