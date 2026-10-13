"""Расчёт состояния товара: просрочен, скоро истекает, низкий остаток или норма.

Это чистые функции без обращения к базе: их легко проверять тестами.
"""

from datetime import date, timedelta
from enum import Enum
from typing import List, Optional

from pharmacy.models import Product


class ProductStatus(Enum):
    """Состояние товара."""

    EXPIRED = "expired"
    EXPIRING = "expiring"
    LOW_STOCK = "low_stock"
    OK = "ok"

    @property
    def label(self) -> str:
        """Название состояния для интерфейса."""
        return _LABELS[self]


_LABELS = {
    ProductStatus.EXPIRED: "Просрочен",
    ProductStatus.EXPIRING: "Скоро истекает",
    ProductStatus.LOW_STOCK: "Низкий остаток",
    ProductStatus.OK: "Норма",
}

# От самого важного к наименее важному: так выбирается главное состояние.
STATUS_PRIORITY = (
    ProductStatus.EXPIRED,
    ProductStatus.EXPIRING,
    ProductStatus.LOW_STOCK,
    ProductStatus.OK,
)


def get_statuses(
    expiry_date: Optional[date],
    quantity: float,
    min_quantity: float,
    warning_days: int,
    today: Optional[date] = None,
    low_threshold: float = 0,
) -> List[ProductStatus]:
    """Определяет все состояния товара.

    Правила из ТЗ:
      * срок вышел, если дата раньше сегодняшней;
      * срок скоро выйдет, если до даты осталось не больше ``warning_days`` дней
        (включая сегодняшний день);
      * остаток низкий, если количество не больше минимального остатка товара,
        а если в настройках уведомлений задан порог низкого остатка, то если
        количество не больше этого порога (от 0 до порога включительно).

    Args:
        expiry_date: Срок годности или None.
        quantity: Количество.
        min_quantity: Минимальный остаток.
        warning_days: За сколько дней предупреждать о сроке.
        today: Сегодняшняя дата (по умолчанию берётся из системы).
        low_threshold: Порог низкого остатка из настроек (0: по минимуму товара).

    Returns:
        Список состояний от самого важного. Если проблем нет, в нём
        одно состояние OK.
    """
    today = today or date.today()
    statuses = []
    if expiry_date is not None:
        if expiry_date < today:
            statuses.append(ProductStatus.EXPIRED)
        elif expiry_date <= today + timedelta(days=warning_days):
            statuses.append(ProductStatus.EXPIRING)
    limit = low_threshold if low_threshold > 0 else min_quantity
    if quantity <= limit:
        statuses.append(ProductStatus.LOW_STOCK)
    return statuses or [ProductStatus.OK]


def product_statuses(
    product: Product,
    warning_days: int,
    today: Optional[date] = None,
    low_threshold: float = 0,
) -> List[ProductStatus]:
    """Определяет состояния товара из объекта Product (см. get_statuses)."""
    return get_statuses(
        product.expiry_date,
        product.quantity,
        product.min_quantity,
        warning_days,
        today,
        low_threshold,
    )


def primary_status(statuses: List[ProductStatus]) -> ProductStatus:
    """Выбирает главное состояние, которое показывается в таблице.

    Args:
        statuses: Список состояний товара.

    Returns:
        Самое важное состояние по порядку STATUS_PRIORITY.
    """
    return next((s for s in STATUS_PRIORITY if s in statuses), ProductStatus.OK)
