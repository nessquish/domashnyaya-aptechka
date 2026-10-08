"""Контейнер сервисов: собирает все сервисы приложения вокруг одной базы."""

from dataclasses import dataclass

from pharmacy.db.connection import Database
from pharmacy.services.auth_service import AuthService
from pharmacy.services.dashboard_service import DashboardService
from pharmacy.services.data_service import DataService
from pharmacy.services.history_service import HistoryService
from pharmacy.services.notification_service import NotificationService
from pharmacy.services.product_service import ProductService
from pharmacy.services.settings_service import SettingsService
from pharmacy.services.shopping_service import ShoppingService


@dataclass(frozen=True)
class Services:
    """Все сервисы приложения.

    Интерфейс получает этот набор целиком и обращается только к нему,
    поэтому экраны не знают ни о базе, ни о том, как сервисы связаны.
    """

    auth: AuthService
    products: ProductService
    notifications: NotificationService
    shopping: ShoppingService
    history: HistoryService
    settings: SettingsService
    dashboard: DashboardService
    data: DataService


def build_services(db: Database) -> Services:
    """Создаёт сервисы и связывает их между собой.

    Сервисы товаров и настроек получают сервис уведомлений, чтобы после
    изменения товара или настроек уведомления пересчитывались сами.

    Args:
        db: Менеджер базы данных.
    """
    notifications = NotificationService(db)
    products = ProductService(db, notifications)
    return Services(
        auth=AuthService(db),
        products=products,
        notifications=notifications,
        shopping=ShoppingService(db),
        history=HistoryService(db),
        settings=SettingsService(db, notifications),
        dashboard=DashboardService(db),
        data=DataService(db, products),
    )
