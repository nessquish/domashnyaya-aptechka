"""Тесты профиля и настроек пользователя."""

from datetime import date, timedelta

from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.services.notification_service import NotificationService
from pharmacy.services.settings_service import SettingsService
from tests.helpers import DatabaseTestCase


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
        self.assertEqual((user.warning_days, user.theme), (30, "light"))
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
        self.assertEqual((other.warning_days, other.theme), (30, "light"))


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
