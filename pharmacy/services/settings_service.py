"""Профиль и настройки пользователя."""

from typing import Optional

from pharmacy.db.connection import Database
from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.models import User
from pharmacy.repositories.user_repository import UserRepository
from pharmacy.services.notification_service import NotificationService
from pharmacy.utils.validation import (
    validate_email,
    validate_login,
    validate_username,
)

THEMES = ("light", "dark")
MIN_WARNING_DAYS = 1
MAX_WARNING_DAYS = 365


class SettingsService:
    """Изменение имени, почты, срока предупреждения, темы и уведомлений."""

    def __init__(
        self, db: Database, notifications: Optional[NotificationService] = None
    ) -> None:
        """Создаёт сервис.

        Args:
            db: Менеджер базы данных.
            notifications: Сервис уведомлений. Он пересчитывается после смены
                настроек, чтобы список уведомлений сразу соответствовал им.
        """
        self._users = UserRepository(db)
        self._notifications = notifications

    def get_user(self, user_id: int) -> User:
        """Возвращает пользователя с текущими настройками.

        Raises:
            NotFoundError: Если пользователя нет.
        """
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Пользователь не найден")
        return user

    def update_profile(
        self,
        user_id: int,
        username: str,
        email: str,
        login: Optional[str] = None,
    ) -> User:
        """Меняет имя, почту и (если указан) логин.

        Raises:
            NotFoundError: Если пользователя нет.
            ValidationError: Если данные неверны либо почта или логин заняты.
        """
        self.get_user(user_id)
        username = validate_username(username)
        email = validate_email(email)
        if self._users.email_used_by_other(email, user_id):
            raise ValidationError("Эта почта уже зарегистрирована", "email")
        if login is not None:
            login = validate_login(login)
            owner = self._users.get_by_login(login)
            if owner is not None and owner.id != user_id:
                raise ValidationError("Этот логин уже занят", "login")
        self._users.update_profile(user_id, username, email, login)
        return self.get_user(user_id)

    def update_settings(
        self,
        user_id: int,
        warning_days: str,
        theme: str,
        notify_expired: bool,
        notify_low_stock: bool,
    ) -> User:
        """Сохраняет настройки и пересчитывает уведомления.

        Args:
            user_id: Пользователь.
            warning_days: За сколько дней предупреждать (целое от 1 до 365).
            theme: ``light`` или ``dark``.
            notify_expired: Уведомлять об истёкшем сроке.
            notify_low_stock: Уведомлять о низком остатке.

        Raises:
            NotFoundError: Если пользователя нет.
            ValidationError: Если число дней или тема неверны.
        """
        self.get_user(user_id)
        days = self._parse_days(warning_days)
        if theme not in THEMES:
            raise ValidationError("Выберите светлую или тёмную тему", "theme")
        self._users.update_settings(
            user_id, days, theme, bool(notify_expired), bool(notify_low_stock)
        )
        if self._notifications is not None:
            self._notifications.refresh(user_id)
        return self.get_user(user_id)

    @staticmethod
    def _parse_days(text: str) -> int:
        """Разбирает число дней предупреждения."""
        try:
            days = int(str(text).strip())
        except ValueError:
            raise ValidationError("Введите целое число дней", "warning_days")
        if not MIN_WARNING_DAYS <= days <= MAX_WARNING_DAYS:
            raise ValidationError(
                f"Число дней от {MIN_WARNING_DAYS} до {MAX_WARNING_DAYS}",
                "warning_days",
            )
        return days
