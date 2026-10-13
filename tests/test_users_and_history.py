"""Пользователи, история и настройки: репозиторий и сервисы."""

import sqlite3
from pharmacy.repositories.user_repository import UserRepository
from tests.helpers import DatabaseTestCase
from datetime import date, timedelta
from pharmacy.models import HistoryAction
from pharmacy.services.history_service import ACTION_LABELS, HistoryService
from pharmacy.services.product_service import ProductForm, ProductService
from pharmacy.services.shopping_service import ShoppingService
from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.services.notification_service import NotificationService
from pharmacy.services.settings_service import SettingsService


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


class HistoryServiceTest(DatabaseTestCase):
    """Просмотр, фильтры и очистка истории."""

    def setUp(self) -> None:
        super().setUp()
        self.service = HistoryService(self.db)
        self.user_id = self.add_user("anna")
        products = ProductService(self.db)
        form = ProductForm(
            name="Бинт", category_id=self.category_id(), quantity="2", unit="шт."
        )
        view = products.add_product(self.user_id, form)
        self.product_id = view.product.id
        ShoppingService(self.db).add_manual(self.user_id, "Вата")

    def test_lists_newest_first(self):
        actions = [r.action for r in self.service.list_history(self.user_id)]
        self.assertEqual(
            actions, [HistoryAction.SHOPPING_ADDED, HistoryAction.PRODUCT_ADDED]
        )

    def test_filter_by_action(self):
        records = self.service.list_history(
            self.user_id, action=HistoryAction.PRODUCT_ADDED
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].product_id, self.product_id)

    def test_limit(self):
        self.assertEqual(len(self.service.list_history(self.user_id, limit=1)), 1)

    def test_filter_by_period(self):
        self.db.execute(
            "UPDATE history SET created_at = '2020-01-01 10:00:00' WHERE action = ?",
            (HistoryAction.PRODUCT_ADDED,),
        )
        recent = self.service.list_history(
            self.user_id, since=date.today() - timedelta(days=7)
        )
        self.assertEqual([r.action for r in recent], [HistoryAction.SHOPPING_ADDED])
        self.assertEqual(len(self.service.list_history(self.user_id)), 2)

    def test_history_survives_product_deletion(self):
        ProductService(self.db).delete_product(self.user_id, self.product_id)
        records = self.service.list_history(
            self.user_id, action=HistoryAction.PRODUCT_ADDED
        )
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0].product_id)

    def test_other_users_do_not_see_my_history(self):
        other_id = self.add_user("boris")
        self.assertEqual(self.service.list_history(other_id), [])

    def test_clear_removes_only_my_records(self):
        other_id = self.add_user("boris")
        ShoppingService(self.db).add_manual(other_id, "Бинт")
        self.assertEqual(self.service.clear(self.user_id), 2)
        self.assertEqual(self.service.list_history(self.user_id), [])
        self.assertEqual(len(self.service.list_history(other_id)), 1)

    def test_every_action_has_a_label(self):
        for action in (
            HistoryAction.PRODUCT_ADDED,
            HistoryAction.PRODUCT_UPDATED,
            HistoryAction.PRODUCT_DELETED,
            HistoryAction.SHOPPING_ADDED,
            HistoryAction.SHOPPING_BOUGHT,
            HistoryAction.SHOPPING_REMOVED,
        ):
            self.assertIn(action, ACTION_LABELS)


class SettingsTestCase(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.notifications = NotificationService(self.db)
        self.service = SettingsService(self.db, self.notifications)
        self.user_id = self.add_user("anna")

    def save(self, **overrides):
        values = dict(
            warning_days="30", theme="light", notify_expired=True, notify_low_stock=True
        )
        values.update(overrides)
        return self.service.update_settings(self.user_id, **values)


class ProfileTest(SettingsTestCase):
    def test_updates_name_and_email(self):
        user = self.service.update_profile(self.user_id, " Анна ", " New@Example.com ")
        self.assertEqual((user.username, user.email), ("Анна", "new@example.com"))

    def test_can_keep_own_email(self):
        user = self.service.update_profile(self.user_id, "Анна", "anna@example.com")
        self.assertEqual(user.email, "anna@example.com")

    def test_email_of_other_user_is_rejected(self):
        self.add_user("boris")
        with self.assertRaises(ValidationError) as ctx:
            self.service.update_profile(self.user_id, "Анна", "BORIS@example.com")
        self.assertEqual(ctx.exception.field, "email")

    def test_invalid_values(self):
        with self.assertRaises(ValidationError) as ctx:
            self.service.update_profile(self.user_id, "", "a@b.ru")
        self.assertEqual(ctx.exception.field, "username")
        with self.assertRaises(ValidationError) as ctx:
            self.service.update_profile(self.user_id, "Анна", "не почта")
        self.assertEqual(ctx.exception.field, "email")

    def test_unknown_user(self):
        with self.assertRaises(NotFoundError):
            self.service.update_profile(999, "Анна", "a@b.ru")
        with self.assertRaises(NotFoundError):
            self.service.get_user(999)


class SettingsTest(SettingsTestCase):
    def test_saves_all_settings(self):
        user = self.save(
            warning_days="45",
            theme="dark",
            notify_expired=False,
            notify_low_stock=False,
        )
        self.assertEqual(user.warning_days, 45)
        self.assertEqual(user.theme, "dark")
        self.assertFalse(user.notify_expired)
        self.assertFalse(user.notify_low_stock)

    def test_defaults_before_first_save(self):
        user = self.service.get_user(self.user_id)
        self.assertEqual((user.warning_days, user.theme), (30, "system"))
        self.assertTrue(user.notify_expired and user.notify_low_stock)

    def test_bad_warning_days(self):
        for text in ("", "abc", "1.5", "0", "-3", "366"):
            with self.assertRaises(ValidationError, msg=text) as ctx:
                self.save(warning_days=text)
            self.assertEqual(ctx.exception.field, "warning_days", text)

    def test_boundary_warning_days(self):
        self.assertEqual(self.save(warning_days="1").warning_days, 1)
        self.assertEqual(self.save(warning_days="365").warning_days, 365)

    def test_bad_theme(self):
        with self.assertRaises(ValidationError) as ctx:
            self.save(theme="pink")
        self.assertEqual(ctx.exception.field, "theme")

    def test_invalid_input_changes_nothing(self):
        self.save(warning_days="10")
        with self.assertRaises(ValidationError):
            self.save(warning_days="10", theme="pink")
        self.assertEqual(self.service.get_user(self.user_id).warning_days, 10)

    def test_changing_settings_refreshes_notifications(self):
        expiry = (date.today() + timedelta(days=20)).isoformat()
        self.add_product(self.user_id, expiry_date=expiry)
        self.save(warning_days="30")
        self.assertEqual(self.count_rows("notifications"), 1)
        self.save(warning_days="10")
        self.assertEqual(self.count_rows("notifications"), 0)

    def test_works_without_notification_service(self):
        service = SettingsService(self.db)
        user = service.update_settings(self.user_id, "7", "dark", True, True)
        self.assertEqual(user.warning_days, 7)

    def test_settings_of_other_users_are_untouched(self):
        other_id = self.add_user("boris")
        self.save(warning_days="5", theme="dark")
        other = self.service.get_user(other_id)
        self.assertEqual((other.warning_days, other.theme), (30, "system"))


class LoginChangeTest(SettingsTestCase):
    def test_login_is_changed(self):
        user = self.service.update_profile(self.user_id, "Анна", "a@b.ru", "anna_new")
        self.assertEqual(user.login, "anna_new")

    def test_own_login_in_other_case_is_allowed(self):
        user = self.service.update_profile(self.user_id, "Анна", "a@b.ru", "ANNA")
        self.assertEqual(user.login.lower(), "anna")

    def test_taken_login_is_rejected(self):
        self.add_user("boris")
        with self.assertRaises(ValidationError) as ctx:
            self.service.update_profile(self.user_id, "Анна", "a@b.ru", "Boris")
        self.assertEqual(ctx.exception.field, "login")

    def test_bad_login_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.service.update_profile(self.user_id, "Анна", "a@b.ru", "я")
