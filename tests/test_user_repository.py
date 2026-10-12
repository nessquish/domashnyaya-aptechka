"""Тесты репозитория пользователей."""

import sqlite3

from pharmacy.repositories.user_repository import UserRepository
from tests.helpers import DatabaseTestCase


class UserRepositoryTest(DatabaseTestCase):
    """Чтение и запись пользователей."""

    def setUp(self) -> None:
        super().setUp()
        self.repo = UserRepository(self.db)

    def test_add_and_get_by_id(self):
        user_id = self.repo.add("anna", "Анна", "anna@mail.ru", "hash")
        user = self.repo.get_by_id(user_id)
        self.assertEqual(user.login, "anna")
        self.assertEqual(user.username, "Анна")
        self.assertEqual(user.warning_days, 30)
        self.assertEqual(user.theme, "system")
        self.assertTrue(user.notify_expired)
        self.assertTrue(user.notify_low_stock)

    def test_unknown_id_returns_none(self):
        self.assertIsNone(self.repo.get_by_id(999))

    def test_get_by_login_ignores_case(self):
        self.repo.add("Anna", "Анна", "anna@mail.ru", "hash")
        self.assertIsNotNone(self.repo.get_by_login("anna"))
        self.assertIsNotNone(self.repo.get_by_login("ANNA"))
        self.assertIsNone(self.repo.get_by_login("boris"))

    def test_email_exists_ignores_case(self):
        self.repo.add("anna", "Анна", "anna@mail.ru", "hash")
        self.assertTrue(self.repo.email_exists("ANNA@mail.ru"))
        self.assertFalse(self.repo.email_exists("other@mail.ru"))

    def test_duplicate_login_raises(self):
        self.repo.add("anna", "Анна", "anna@mail.ru", "hash")
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.add("anna", "Другая", "other@mail.ru", "hash")

    def test_update_password_hash(self):
        user_id = self.repo.add("anna", "Анна", "anna@mail.ru", "old")
        self.repo.update_password_hash(user_id, "new")
        self.assertEqual(self.repo.get_by_id(user_id).password_hash, "new")

    def test_sql_injection_in_login_is_harmless(self):
        self.repo.add("anna", "Анна", "anna@mail.ru", "hash")
        self.assertIsNone(self.repo.get_by_login("' OR '1'='1"))
        self.assertEqual(self.count_rows("users"), 1)
