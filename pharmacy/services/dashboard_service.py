"""Сводка для главного экрана: счётчики, что требует внимания, последние действия."""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from pharmacy.db.connection import Database
from pharmacy.models import HistoryRecord
from pharmacy.repositories.history_repository import HistoryRepository
from pharmacy.repositories.notification_repository import NotificationRepository
from pharmacy.repositories.shopping_repository import ShoppingRepository
from pharmacy.services.product_service import ProductService, ProductView
from pharmacy.services.status import STATUS_PRIORITY, ProductStatus

ATTENTION_LIMIT = 5
RECENT_HISTORY_LIMIT = 5
RECENT_PRODUCTS_LIMIT = 5


@dataclass
class DashboardSummary:
    """Данные главного экрана.

    Товар с двумя проблемами (например, срок и остаток) учитывается в обоих
    счётчиках, поэтому сумма счётчиков может быть больше ``total``.

    Attributes:
        total: Всего товаров в аптечке.
        expired: Сколько товаров просрочено.
        expiring: Сколько товаров скоро истекает.
        low_stock: Сколько товаров с низким остатком.
        attention_total: Сколько товаров требуют внимания (все с проблемой).
        attention: Пять самых срочных из них, самые срочные первыми.
        recent_products: Последние добавленные товары, новые первыми.
        recent_history: Последние действия.
        unread_notifications: Число непрочитанных уведомлений.
        shopping_open: Сколько позиций в списке покупок ещё не куплено.
    """

    total: int = 0
    expired: int = 0
    expiring: int = 0
    low_stock: int = 0
    attention_total: int = 0
    attention: List[ProductView] = field(default_factory=list)
    recent_products: List[ProductView] = field(default_factory=list)
    recent_history: List[HistoryRecord] = field(default_factory=list)
    unread_notifications: int = 0
    shopping_open: int = 0


def _attention_key(view: ProductView):
    """Порядок «требует внимания»: важное состояние, затем меньше дней до срока."""
    rank = STATUS_PRIORITY.index(view.primary_status)
    days = view.days_left if view.days_left is not None else 10**9
    return rank, days, view.product.name.casefold()


class DashboardService:
    """Собирает сводку из товаров, истории, уведомлений и списка покупок."""

    def __init__(self, db: Database, products: Optional[ProductService] = None) -> None:
        """Создаёт сервис.

        Args:
            db: Менеджер базы данных.
            products: Сервис товаров (общий, чтобы учитывать порог низкого остатка).
        """
        self._products = products or ProductService(db)
        self._history = HistoryRepository(db)
        self._notifications = NotificationRepository(db)
        self._shopping = ShoppingRepository(db)

    def summary(self, user_id: int, today: Optional[date] = None) -> DashboardSummary:
        """Возвращает сводку для главного экрана.

        Args:
            user_id: Пользователь.
            today: Сегодняшняя дата (по умолчанию из системы).
        """
        views = self._products.list_products(user_id, today=today)

        def count(status: ProductStatus) -> int:
            return sum(1 for view in views if status in view.statuses)

        problem = [v for v in views if v.primary_status != ProductStatus.OK]
        problem.sort(key=_attention_key)
        return DashboardSummary(
            total=len(views),
            expired=count(ProductStatus.EXPIRED),
            expiring=count(ProductStatus.EXPIRING),
            low_stock=count(ProductStatus.LOW_STOCK),
            attention_total=len(problem),
            attention=problem[:ATTENTION_LIMIT],
            recent_products=self._products.list_products(
                user_id, sort="added", today=today
            )[:RECENT_PRODUCTS_LIMIT],
            recent_history=self._history.list_for_user(
                user_id, limit=RECENT_HISTORY_LIMIT
            ),
            unread_notifications=self._notifications.count_unread(user_id),
            shopping_open=len(self._shopping.list_for_user(user_id, is_bought=False)),
        )
