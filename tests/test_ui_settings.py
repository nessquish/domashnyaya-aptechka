"""Тесты экрана «Настройки»: слева список разделов, справа содержимое."""

from unittest import mock

from pharmacy.ui import sections, theme
from pharmacy.ui.preferences import GLOBAL_USER, MENU_ICONS, SCALE_MODE, SCALE_PERCENT
from pharmacy.ui.screens.settings import (
    ABOUT,
    ACCOUNT,
    APPEARANCE,
    DATA,
    HINT,
    NOTIFICATIONS,
    SECTIONS,
    SettingsScreen,
)
from tests.qt_helpers import ShellTestCase, click

PASSWORD = "demo12345"


class SettingsTestCase(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.shell.navigate(sections.SETTINGS)
        self.settle()

    @property
    def screen_(self) -> SettingsScreen:
        return self.page

    def section(self, key):
        self.page.open_section(key)
        self.settle()
        return self.page

    def user(self):
        return self.services.settings.get_user(self.app.user.id)

    def prefs(self, key, default=None):
        return self.app.preferences.get(self.app.user.id, key, default)


class LayoutTest(SettingsTestCase):
    def test_nothing_is_selected_at_first(self):
        self.assertIsInstance(self.page, SettingsScreen)
        self.assertIsNone(self.page.section)
        self.assertEqual(self.page.hint.text(), HINT)
        self.assertEqual(HINT, "Выберите настройку")

    def test_sections_are_listed_in_order(self):
        names = [title for _key, title, _icon in SECTIONS]
        self.assertEqual(
            names,
            ["Внешний вид", "Уведомления", "Данные", "Аккаунт", "О программе"],
        )

    def test_choosing_a_section_hides_the_hint(self):
        self.section(NOTIFICATIONS)
        self.assertEqual(self.page.section, NOTIFICATIONS)
        self.assertIsNone(self.page.hint)

    def test_clicking_the_list_opens_the_section(self):
        click(self.page._items[DATA])
        self.settle()
        self.assertEqual(self.page.section, DATA)
        self.assertTrue(self.page._items[DATA].active)
        self.assertFalse(self.page._items[ABOUT].active)

    def test_unknown_section_is_rejected(self):
        with self.assertRaises(ValueError):
            self.page.open_section("nope")


class AppearanceTest(SettingsTestCase):
    def test_theme_choice_applies_at_once(self):
        page = self.section(APPEARANCE)
        left, right = page.theme_switch.spans[1]
        click(page.theme_switch, (left + right) // 2, 10)
        self.settle()
        self.assertEqual(theme.theme_name(), "dark")
        self.assertEqual(self.page.section, APPEARANCE)  # раздел остался открыт

    def test_system_theme_can_be_chosen(self):
        page = self.section(APPEARANCE)
        self.assertEqual(len(page.theme_switch._items), 3)
        self.shell.set_theme("system")
        self.settle()
        self.assertEqual(self.app.theme_mode(self.app.user), "system")

    def test_scale_defaults_to_auto_and_slider_is_hidden(self):
        page = self.section(APPEARANCE)
        self.assertEqual(page.scale_switch.active, 0)
        self.assertFalse(page._slider_row.isVisible())

    def test_manual_scale_shows_the_slider_and_is_saved(self):
        page = self.section(APPEARANCE)
        page._on_scale_mode(1)
        self.settle()
        self.assertTrue(page._slider_row.isVisible())
        self.assertEqual(self.app.preferences.get(GLOBAL_USER, SCALE_MODE), "manual")
        page._on_slider_done(125)
        self.assertEqual(self.app.preferences.get(GLOBAL_USER, SCALE_PERCENT), 125)

    def test_slider_range_is_80_to_150(self):
        page = self.section(APPEARANCE)
        self.assertEqual((page.scale_slider._min, page.scale_slider._max), (80, 150))

    def test_text_size_has_three_steps(self):
        page = self.section(APPEARANCE)
        self.assertEqual(page.text_size_switch._items, ["Мелкий", "Средний", "Крупный"])

    def test_menu_icons_toggle_is_remembered(self):
        page = self.section(APPEARANCE)
        self.assertTrue(page.icons_toggle.value)
        page._on_menu_icons(False)
        self.settle()
        self.assertFalse(self.prefs(MENU_ICONS))
        self.assertIsNone(self.shell.sidebar.item(sections.HOME)._icon)
        self.assertEqual(self.page.section, APPEARANCE)

    def test_accent_color_is_marked_as_coming_soon(self):
        from pharmacy.ui.widgets.badge import Badge
        from tests.qt_helpers import find_all

        self.section(APPEARANCE)
        self.assertIn("Скоро", [b.text for b in find_all(self.page, Badge)])


class NotificationsTest(SettingsTestCase):
    def test_flags_are_saved(self):
        page = self.section(NOTIFICATIONS)
        click(page.expired_toggle)
        self.assertFalse(self.user().notify_expired)
        click(page.low_toggle)
        self.assertFalse(self.user().notify_low_stock)

    def test_master_switch_removes_all_notifications(self):
        page = self.section(NOTIFICATIONS)
        self.assertTrue(
            self.services.notifications.list_notifications(self.app.user.id)
        )
        page._on_master(False)
        self.assertEqual(
            self.services.notifications.list_notifications(self.app.user.id), []
        )
        page._on_master(True)
        self.assertTrue(
            self.services.notifications.list_notifications(self.app.user.id)
        )

    def test_days_are_saved_when_valid(self):
        page = self.section(NOTIFICATIONS)
        page.days_field.set("14")
        page._days_edited()
        self.assertEqual(self.user().warning_days, 14)

    def test_days_above_30_are_rejected(self):
        page = self.section(NOTIFICATIONS)
        before = self.user().warning_days
        page.days_field.set("31")
        page._days_edited()
        self.assertEqual(self.user().warning_days, before)
        self.assertIn("от 1 до 30", page._days_hint.text())

    def test_days_zero_and_text_are_rejected(self):
        page = self.section(NOTIFICATIONS)
        for bad in ("0", "abc", ""):
            page.days_field.set(bad)
            page._days_edited()
            self.assertIn("от 1 до 30", page._days_hint.text(), bad)

    def test_expiring_switch_is_remembered_and_applied(self):
        page = self.section(NOTIFICATIONS)
        kinds = lambda: {  # noqa: E731
            n.kind
            for n in self.services.notifications.list_notifications(self.app.user.id)
        }
        self.assertIn("expiring", kinds())
        page._on_expiring(False)
        self.assertFalse(self.prefs("notify_expiring"))
        self.assertNotIn("expiring", kinds())

    def test_low_threshold_adds_low_stock_notifications(self):
        page = self.section(NOTIFICATIONS)
        before = len(self.services.notifications.list_notifications(self.app.user.id))
        page.threshold_field.set("1000")
        page._threshold_edited()
        after = len(self.services.notifications.list_notifications(self.app.user.id))
        self.assertEqual(self.prefs("low_threshold"), 1000)
        self.assertGreaterEqual(after, before)

    def test_bad_threshold_is_marked(self):
        page = self.section(NOTIFICATIONS)
        page.threshold_field.set("-3")
        page._threshold_edited()
        self.assertIn("не меньше нуля", page._low_hint.text())


class DataTest(SettingsTestCase):
    def kit_count(self):
        return len(self.services.products.list_products(self.app.user.id))

    def test_export_writes_a_file(self):
        import tempfile
        from pathlib import Path

        page = self.section(DATA)
        with tempfile.TemporaryDirectory() as folder:
            target = str(Path(folder) / "out.json")
            with mock.patch.object(page, "_choose_save_path", return_value=target):
                page._export("json")
            self.assertTrue(Path(target).exists())
        self.assertIsNotNone(page.notice)

    def test_cancelled_export_does_nothing(self):
        page = self.section(DATA)
        with mock.patch.object(page, "_choose_save_path", return_value=""):
            page._export("csv")
        self.assertIsNone(page.notice)

    def test_import_adds_products(self):
        import tempfile
        from pathlib import Path

        page = self.section(DATA)
        before = self.kit_count()
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "in.json"
            source.write_text(
                '[{"name": "Новый тест", "category": "Лекарства", "quantity": 2,'
                ' "unit": "шт.", "expiry_date": "", "min_quantity": 1}]',
                encoding="utf-8",
            )
            with mock.patch.object(page, "_choose_open_path", return_value=str(source)):
                page._import()
        self.settle()
        self.assertEqual(self.kit_count(), before + 1)

    def test_clear_history_asks_first(self):
        page = self.section(DATA)
        page.clear_history_button.invoke()
        self.settle()
        self.assertTrue(self.buttons("Очистить"))
        self.assertTrue(self.services.history.list_history(self.app.user.id))
        page._clear_history()
        self.assertEqual(self.services.history.list_history(self.app.user.id), [])

    def test_reset_removes_everything_but_the_account(self):
        page = self.section(DATA)
        page.reset_button.invoke()
        self.settle()
        self.assertTrue(self.buttons("Сбросить"))
        self.assertGreater(self.kit_count(), 0)
        page._reset()
        self.settle()
        self.assertEqual(self.kit_count(), 0)
        self.assertEqual(self.services.shopping.list_items(self.app.user.id), [])
        self.assertEqual(self.services.history.list_history(self.app.user.id), [])
        self.assertEqual(
            self.services.notifications.list_notifications(self.app.user.id), []
        )
        self.assertIsNotNone(self.user())


class AccountTest(SettingsTestCase):
    def test_shows_the_account(self):
        self.section(ACCOUNT)
        texts = [
            w.text()
            for w in self.page.findChildren(
                __import__("PySide6.QtWidgets", fromlist=["QLabel"]).QLabel
            )
        ]
        self.assertIn("nessquish", texts)
        self.assertIn("Анастасия", texts)

    def test_profile_modal_saves_name_and_email(self):
        page = self.section(ACCOUNT)
        page.edit_email_button.invoke()
        self.settle()
        modal = page.profile_modal
        modal.fields["username"].set("Анна")
        modal.fields["email"].set("new@mail.ru")
        modal._submit()
        self.settle()
        self.assertEqual(
            (self.user().username, self.user().email), ("Анна", "new@mail.ru")
        )
        self.assertEqual(self.page.section, ACCOUNT)

    def test_profile_modal_marks_a_bad_email(self):
        page = self.section(ACCOUNT)
        page.edit_email_button.invoke()
        self.settle()
        modal = page.profile_modal
        modal.fields["email"].set("не почта")
        modal._submit()
        self.assertTrue(modal.is_open)
        self.assertIsNotNone(modal.fields["email"].error)

    def test_password_modal_changes_the_password(self):
        page = self.section(ACCOUNT)
        page.password_button.invoke()
        self.settle()
        modal = page.password_modal
        modal.fields["old_password"].set(PASSWORD)
        modal.fields["new_password"].set("newpass123")
        modal.fields["new_password_repeat"].set("newpass123")
        modal._submit()
        self.settle()
        self.services.auth.login("nessquish", "newpass123")

    def test_wrong_old_password_is_marked(self):
        page = self.section(ACCOUNT)
        page.password_button.invoke()
        self.settle()
        modal = page.password_modal
        modal.fields["old_password"].set("wrong-password")
        modal.fields["new_password"].set("newpass123")
        modal.fields["new_password_repeat"].set("newpass123")
        modal._submit()
        self.assertTrue(modal.is_open)
        self.assertIsNotNone(modal.fields["old_password"].error)

    def test_mismatch_is_marked(self):
        page = self.section(ACCOUNT)
        page.password_button.invoke()
        self.settle()
        modal = page.password_modal
        modal.fields["old_password"].set(PASSWORD)
        modal.fields["new_password"].set("newpass123")
        modal.fields["new_password_repeat"].set("other12345")
        modal._submit()
        self.assertTrue(modal.is_open)

    def test_logout_asks_for_confirmation(self):
        page = self.section(ACCOUNT)
        page.logout_button.invoke()
        self.settle()
        self.assertIsNotNone(self.app.user)
        self.assertTrue(self.buttons("Выйти"))

    def test_deleting_the_account_needs_two_confirmations(self):
        page = self.section(ACCOUNT)
        page.delete_button.invoke()
        self.settle()
        self.assertTrue(self.buttons("Продолжить"))
        self.buttons("Продолжить")[0].invoke()
        self.settle()
        self.assertTrue(self.buttons("Удалить навсегда"))
        self.assertIsNotNone(self.app.user)
        self.buttons("Удалить навсегда")[0].invoke()
        self.settle()
        self.assertIsNone(self.app.user)
        self.assertIsNone(self.services.auth._users.get_by_login("nessquish"))


class AboutTest(SettingsTestCase):
    def test_shows_name_version_date_and_developer(self):
        from PySide6.QtWidgets import QLabel

        from pharmacy import __build_date__, __developer__, __version__

        self.section(ABOUT)
        texts = [w.text() for w in self.page.findChildren(QLabel)]
        for expected in ("Моя аптечка", __version__, __build_date__, __developer__):
            self.assertIn(expected, texts)

    def test_guide_button_opens_the_repository(self):
        page = self.section(ABOUT)
        with mock.patch(
            "pharmacy.ui.screens.settings.QDesktopServices.openUrl"
        ) as opener:
            page.guide_button.invoke()
        self.assertIn(
            "github.com/nessquish/aptechka", opener.call_args[0][0].toString()
        )


class ReopenTest(SettingsTestCase):
    def test_section_survives_a_rebuild(self):
        self.section(NOTIFICATIONS)
        self.page._rebuild()
        self.settle()
        self.assertEqual(self.page.section, NOTIFICATIONS)
