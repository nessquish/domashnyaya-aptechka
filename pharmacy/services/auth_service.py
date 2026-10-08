"""Регистрация, вход и смена пароля."""

import sqlite3

from pharmacy.db.connection import Database
from pharmacy.errors import AuthenticationError, NotFoundError, ValidationError
from pharmacy.models import User
from pharmacy.repositories.user_repository import UserRepository
from pharmacy.utils.security import hash_password, verify_password
from pharmacy.utils.validation import (
    validate_email,
    validate_login,
    validate_password,
    validate_username,
)

NO_ACCOUNT = "Аккаунт с таким логином или почтой не найден"
WRONG_PASSWORD = "Неверный пароль"


NO_ACCOUNT = "Аккаунт с таким логином или почтой не найден"
WRONG_PASSWORD = "Неверный пароль"


class AuthService:
    """Правила работы с учётными записями."""

    def __init__(self, db: Database) -> None:
        """Создаёт сервис.

        Args:
            db: Менеджер базы данных.
        """
        self._users = UserRepository(db)

    def register(
        self,
        login: str,
        username: str,
        email: str,
        password: str,
        password_repeat: str,
    ) -> User:
        """Регистрирует нового пользователя.

        Args:
            login: Логин.
            username: Имя пользователя. Если не введено, используется логин.
            email: Электронная почта.
            password: Пароль.
            password_repeat: Повтор пароля.

        Returns:
            Созданный пользователь.

        Raises:
            ValidationError: Если данные неверны или логин/почта уже заняты.
        """
        login = validate_login(login)
        username = validate_username(username.strip() or login)
        email = validate_email(email)
        validate_password(password, password_repeat)
        if self._users.get_by_login(login):
            raise ValidationError("Этот логин уже занят", "login")
        if self._users.email_exists(email):
            raise ValidationError("Эта почта уже зарегистрирована", "email")
        try:
            user_id = self._users.add(login, username, email, hash_password(password))
        except sqlite3.IntegrityError as error:
            # Страховка: между проверкой и записью логин мог занять другой процесс.
            raise ValidationError("Логин или почта уже заняты") from error
        return self._require_user(user_id)

    def login(self, login: str, password: str) -> User:
        """Проверяет логин (или почту) и пароль.

        Args:
            login: Логин или адрес электронной почты на выбор пользователя.
                В логине не бывает «@», поэтому они не путаются.
            password: Пароль.

        Returns:
            Пользователь, который вошёл.

        Raises:
            ValidationError: Если логин или пароль не введены.
            AuthenticationError: Если аккаунта нет (поле ``login``) или пароль
                не подошёл (поле ``password``): интерфейс подсвечивает это поле.
        """
        login = login.strip()
        if not login:
            raise ValidationError("Введите логин или эл. почту", "login")
        if not password:
            raise ValidationError("Введите пароль", "password")
        if "@" in login:
            user = self._users.get_by_email(login)
        else:
            user = self._users.get_by_login(login)
        if user is None:
            raise AuthenticationError(NO_ACCOUNT, "login")
        if not verify_password(password, user.password_hash):
            raise AuthenticationError(WRONG_PASSWORD, "password")
        return user

    def change_password(
        self,
        user_id: int,
        old_password: str,
        new_password: str,
        new_password_repeat: str,
    ) -> None:
        """Меняет пароль пользователя.

        Args:
            user_id: Идентификатор пользователя.
            old_password: Текущий пароль.
            new_password: Новый пароль.
            new_password_repeat: Повтор нового пароля.

        Raises:
            NotFoundError: Если пользователя нет.
            ValidationError: Если текущий пароль неверен или новый не подходит.
        """
        user = self._require_user(user_id)
        if not verify_password(old_password, user.password_hash):
            raise ValidationError("Текущий пароль указан неверно", "old_password")
        validate_password(new_password, new_password_repeat, field="new_password")
        self._users.update_password_hash(user_id, hash_password(new_password))

    def delete_account(self, user_id: int) -> None:
        """Удаляет аккаунт вместе со всеми данными пользователя.

        Raises:
            NotFoundError: Если пользователя нет.
        """
        self._require_user(user_id)
        self._users.delete(user_id)

    def _require_user(self, user_id: int) -> User:
        """Возвращает пользователя или выбрасывает NotFoundError."""
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Пользователь не найден")
        return user
