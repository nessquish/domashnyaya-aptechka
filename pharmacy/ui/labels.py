"""Подписи и тона для показа данных: состояния, категории, приветствие."""

from typing import Dict, Tuple

from pharmacy.models import HistoryAction, NotificationKind
from pharmacy.services.status import ProductStatus

# Состояние товара -> цвет плашки, значок и тон значка.
STATUS_TONES: Dict[ProductStatus, str] = {
    ProductStatus.EXPIRED: "red",
    ProductStatus.EXPIRING: "amber",
    ProductStatus.LOW_STOCK: "amber",
    ProductStatus.OK: "green",
}
STATUS_ICONS: Dict[ProductStatus, str] = {
    ProductStatus.EXPIRED: "alert",
    ProductStatus.EXPIRING: "clock",
    ProductStatus.LOW_STOCK: "trending-down",
    ProductStatus.OK: "check",
}

# Вид уведомления -> значок и тон значка.
NOTIFICATION_ICONS: Dict[str, str] = {
    NotificationKind.EXPIRED: "alert",
    NotificationKind.EXPIRING: "clock",
    NotificationKind.LOW_STOCK: "trending-down",
}
NOTIFICATION_TONES: Dict[str, str] = {
    NotificationKind.EXPIRED: "red",
    NotificationKind.EXPIRING: "amber",
    NotificationKind.LOW_STOCK: "amber",
}

# Действие в истории -> значок и тон значка.
HISTORY_ICONS: Dict[str, str] = {
    HistoryAction.PRODUCT_ADDED: "plus",
    HistoryAction.PRODUCT_UPDATED: "pencil",
    HistoryAction.PRODUCT_DELETED: "x",
    HistoryAction.SHOPPING_ADDED: "cart",
    HistoryAction.SHOPPING_BOUGHT: "check",
    HistoryAction.SHOPPING_REMOVED: "x",
}
HISTORY_TONES: Dict[str, str] = {
    HistoryAction.PRODUCT_ADDED: "green",
    HistoryAction.PRODUCT_UPDATED: "primary",
    HistoryAction.PRODUCT_DELETED: "red",
    HistoryAction.SHOPPING_ADDED: "amber",
    HistoryAction.SHOPPING_BOUGHT: "green",
    HistoryAction.SHOPPING_REMOVED: "gray",
}

# Короткие названия категорий для таблиц и подписей, как в макете.
_SHORT_CATEGORIES = {
    "Медицинские товары": "Мед. товары",
    "Средства гигиены": "Гигиена",
}

# (час начала, приветствие): выбирается последнее подходящее по времени суток.
_GREETINGS: Tuple[Tuple[int, str], ...] = (
    (0, "Доброй ночи"),
    (5, "Доброе утро"),
    (12, "Добрый день"),
    (18, "Добрый вечер"),
    (23, "Доброй ночи"),
)


def short_category(name: str) -> str:
    """Возвращает короткое название категории (или само название)."""
    return _SHORT_CATEGORIES.get(name, name)


def greeting(hour: int) -> str:
    """Возвращает приветствие по часу суток (0-23)."""
    return next(phrase for start, phrase in reversed(_GREETINGS) if hour >= start)
