"""История действий пользователя: просмотр с фильтрами и очистка."""

from datetime import date
from typing import List, Optional

from pharmacy.db.connection import Database
from pharmacy.models import HistoryAction, HistoryRecord
from pharmacy.repositories.history_repository import HistoryRepository
from pharmacy.utils.textmatch import name_matches

# Подписи видов действий для фильтра в интерфейсе.
ACTION_LABELS = {
    HistoryAction.PRODUCT_ADDED: "Добавление товара",
    HistoryAction.PRODUCT_UPDATED: "Изменение товара",
    HistoryAction.PRODUCT_DELETED: "Удаление товара",
    HistoryAction.SHOPPING_ADDED: "Добавлено в список покупок",
    HistoryAction.SHOPPING_BOUGHT: "Товар куплен",
    HistoryAction.SHOPPING_REMOVED: "Удалено из списка покупок",
}


class HistoryService:
    """Чтение и очистка истории. Записи создают другие сервисы."""

    def __init__(self, db: Database) -> None:
        """Создаёт сервис.

        Args:
            db: Менеджер базы данных.
        """
        self._history = HistoryRepository(db)

    def list_history(
        self,
        user_id: int,
        action: Optional[str] = None,
        since: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[HistoryRecord]:
        """Возвращает историю пользователя, самые новые записи первыми.

        Args:
            user_id: Пользователь.
            action: Только этого вида (см. ACTION_LABELS).
            since: Только не раньше этой даты (фильтр «Период»).
            limit: Не больше стольких записей.
        """
        return self._history.list_for_user(user_id, action, limit, since)

    def search(self, user_id: int, query: str, limit: int = 10) -> List[HistoryRecord]:
        """Ищет записи истории по описанию (в нём есть название товара)."""
        found = [
            record
            for record in self._history.list_for_user(user_id)
            if name_matches(record.description, query)
        ]
        return found[:limit]

    def clear(self, user_id: int) -> int:
        """Очищает историю пользователя и возвращает число удалённых записей."""
        return self._history.delete_all(user_id)
