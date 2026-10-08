"""Уведомления о состоянии товаров: создание, чтение, отметка прочитанными.

Уведомления создаются из текущего состояния товаров, поэтому они всегда
отражают реальность: пока срок не продлён или запас не пополнен, уведомление
остаётся (и появляется снова при следующем входе, даже если его удалили).
Когда причина исчезает, уведомление удаляется само.
"""

from dataclasses import dataclass
from datetime import date
from typing import Callable, Dict, List, Optional, Tuple

from pharmacy.db.connection import Database
from pharmacy.errors import NotFoundError
from pharmacy.models import Notification, NotificationKind, Product
from pharmacy.repositories.notification_repository import NotificationRepository
from pharmacy.repositories.product_repository import ProductRepository
from pharmacy.repositories.user_repository import UserRepository
from pharmacy.services.status import ProductStatus, product_statuses
from pharmacy.utils.dates import days_until, format_user_date
from pharmacy.utils.formatting import format_quantity, plural

# Подписи видов уведомлений для заголовка и фильтра в интерфейсе.
KIND_LABELS = {
    NotificationKind.EXPIRED: "Срок годности истёк",
    NotificationKind.EXPIRING: "Скоро истекает срок годности",
    NotificationKind.LOW_STOCK: "Низкий остаток",
}

_Key = Tuple[int, str]


def _expired_message(product: Product) -> str:
    """Текст уведомления об истёкшем сроке."""
    text = f"{product.name} · истёк {format_user_date(product.expiry_date)}"
    if product.storage_place:
        text += f" · {product.storage_place}"
    return text


def _expiring_message(product: Product, today: Optional[date]) -> str:
    """Текст уведомления о скором окончании срока."""
    left = days_until(product.expiry_date, today)
    days = plural(left, "день", "дня", "дней")
    return (
        f"{product.name} · до {format_user_date(product.expiry_date)}"
        f" · осталось {left} {days}"
    )


def _low_stock_message(product: Product) -> str:
    """Текст уведомления о низком остатке."""
    return (
        f"{product.name} · осталось {format_quantity(product.quantity)}"
        f" {product.unit} (минимум {format_quantity(product.min_quantity)}"
        f" {product.unit})"
    )


@dataclass(frozen=True)
class NotifyOptions:
    """Общие настройки уведомлений поверх настроек пользователя в базе.

    Attributes:
        enabled: Уведомления включены вообще.
        expiring: Предупреждать о скором окончании срока.
        low_threshold: Считать остаток низким, если он меньше этого числа
            (0 означает «только по минимальному остатку самого товара»).
    """

    enabled: bool = True
    expiring: bool = True
    low_threshold: float = 0.0


class NotificationService:
    """Правила создания и чтения уведомлений."""

    def __init__(self, db: Database) -> None:
        """Создаёт сервис.

        Args:
            db: Менеджер базы данных.
        """
        self._db = db
        self._notifications = NotificationRepository(db)
        self._products = ProductRepository(db)
        self._users = UserRepository(db)
        # Интерфейс подставляет сюда настройки пользователя из его предпочтений.
        self.options_for: Callable[[int], NotifyOptions] = lambda _id: NotifyOptions()

    def refresh(
        self,
        user_id: int,
        today: Optional[date] = None,
        product_id: Optional[int] = None,
    ) -> int:
        """Приводит уведомления в соответствие с состоянием товаров.

        Новые причины получают уведомление, у существующих обновляется текст,
        а уведомления, причина которых пропала, удаляются. Прочитанные
        уведомления остаются прочитанными.

        Правила настроек: уведомления об истёкшем сроке и о низком остатке
        можно отключить в настройках, а уведомление «скоро истекает» зависит
        только от числа дней предупреждения.

        Args:
            user_id: Пользователь.
            today: Сегодняшняя дата (по умолчанию из системы).
            product_id: Если указан, пересчитывается только этот товар
                (после его добавления или изменения), иначе все товары.

        Returns:
            Сколько новых уведомлений создано.

        Raises:
            NotFoundError: Если пользователя нет.
        """
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Пользователь не найден")
        if product_id is None:
            products = self._products.list_for_user(user_id)
        else:
            single = self._products.get(user_id, product_id)
            products = [single] if single else []

        options = self.options_for(user_id)
        desired: Dict[_Key, str] = {}
        for product in products if options.enabled else []:
            statuses = product_statuses(product, user.warning_days, today)
            if ProductStatus.EXPIRED in statuses and user.notify_expired:
                desired[(product.id, NotificationKind.EXPIRED)] = _expired_message(
                    product
                )
            if ProductStatus.EXPIRING in statuses and options.expiring:
                desired[(product.id, NotificationKind.EXPIRING)] = _expiring_message(
                    product, today
                )
            low = ProductStatus.LOW_STOCK in statuses or (
                options.low_threshold > 0 and product.quantity < options.low_threshold
            )
            if low and user.notify_low_stock:
                desired[(product.id, NotificationKind.LOW_STOCK)] = _low_stock_message(
                    product
                )

        existing = {
            (item.product_id, item.kind): item
            for item in self._notifications.list_for_user(user_id)
        }
        created = 0
        with self._db.transaction() as conn:
            for key, message in desired.items():
                current = existing.get(key)
                if current is None:
                    self._notifications.add(user_id, key[0], key[1], message, conn)
                    created += 1
                elif current.message != message:
                    self._notifications.update_message(current.id, message, conn)
            for key, item in existing.items():
                in_scope = product_id is None or key[0] == product_id
                if in_scope and key not in desired:
                    self._notifications.delete(user_id, item.id, conn)
        return created

    def list_notifications(
        self,
        user_id: int,
        kind: Optional[str] = None,
        unread_only: bool = False,
        since: Optional[date] = None,
    ) -> List[Notification]:
        """Возвращает уведомления пользователя (самые новые первыми).

        Args:
            user_id: Пользователь.
            kind: Только этого вида.
            unread_only: Только непрочитанные.
            since: Только созданные не раньше этой даты (фильтр «Период»).
        """
        return self._notifications.list_for_user(user_id, kind, unread_only, since)

    def count_unread(self, user_id: int) -> int:
        """Возвращает число непрочитанных (для счётчика в боковом меню)."""
        return self._notifications.count_unread(user_id)

    def mark_read(self, user_id: int, notification_id: int) -> None:
        """Отмечает уведомление прочитанным.

        Raises:
            NotFoundError: Если уведомления нет или оно чужое.
        """
        if not self._notifications.mark_read(user_id, notification_id):
            raise NotFoundError("Уведомление не найдено")

    def mark_all_read(self, user_id: int) -> int:
        """Отмечает все уведомления прочитанными и возвращает их число."""
        return self._notifications.mark_all_read(user_id)

    def delete(self, user_id: int, notification_id: int) -> None:
        """Удаляет уведомление.

        Raises:
            NotFoundError: Если уведомления нет или оно чужое.
        """
        if not self._notifications.delete(user_id, notification_id):
            raise NotFoundError("Уведомление не найдено")

    def delete_all(self, user_id: int) -> int:
        """Удаляет все уведомления пользователя и возвращает их число."""
        return self._notifications.delete_all(user_id)
