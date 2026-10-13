"""Тесты размера текста, предпочтений и сворачивания боковой панели."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pharmacy.ui import fonts, runtime, sections, theme
from pharmacy.ui.preferences import Preferences
from pharmacy.ui.screens.settings import SettingsScreen
from pharmacy.ui.widgets.iconbutton import IconButton
from tests.qt_helpers import ShellTestCase, click, find_all


class PreferencesTest(unittest.TestCase):
    def path(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name) / "preferences.json"

    def test_defaults_when_nothing_is_saved(self):
        prefs = Preferences(self.path())
        self.assertEqual(prefs.get(1, "text_size", "normal"), "normal")
        self.assertIsNone(prefs.get(1, "anything"))

    def test_saves_to_file_and_loads_back(self):
        path = self.path()
        Preferences(path).set(1, "text_size", "large")
        self.assertEqual(Preferences(path).get(1, "text_size"), "large")
        self.assertEqual(
            json.loads(path.read_text(encoding="utf-8"))["1"]["text_size"], "large"
        )

    def test_every_user_has_own_values(self):
        prefs = Preferences(self.path())
        prefs.set(1, "text_size", "large")
        prefs.set(2, "text_size", "medium")
        self.assertEqual(prefs.get(1, "text_size"), "large")
        self.assertEqual(prefs.get(2, "text_size"), "medium")
        self.assertIsNone(prefs.get(3, "text_size"))


class TextSizeInAppTest(ShellTestCase):
    def pick(self, index):
        switch = self.page.text_size_switch
        left, right = switch.spans[index]
        click(switch, (left + right) // 2, switch.height() // 2)
        self.settle()

    def open_settings(self):
        self.open(sections.SETTINGS)
        self.page.open_section("appearance")

    def test_settings_offer_three_sizes(self):
        self.open_settings()
        page = self.page
        self.assertIsInstance(page, SettingsScreen)
        self.assertEqual(page.text_size_switch._items, ["Мелкий", "Средний", "Крупный"])
        self.assertEqual(page.text_size_switch.active, 0)

    def test_choice_applies_at_once_and_is_remembered(self):
        self.open_settings()
        self.pick(2)
        self.assertEqual(theme.text_size_name(), "large")
        self.assertEqual(
            self.app.preferences.get(self.app.user.id, "text_size"), "large"
        )
        self.assertEqual(self.shell.section, sections.SETTINGS)
        self.assertEqual(self.page.text_size_switch.active, 2)

    def test_window_widens_for_larger_text(self):
        with mock.patch.object(runtime, "screen_size", return_value=(2560, 1440)):
            self.open_settings()
            before = self.app.minimumWidth()
            self.pick(2)
            self.assertGreater(self.app.minimumWidth(), before)
            self.assertGreaterEqual(self.app.width(), theme.window_width())

    def test_text_really_gets_bigger(self):
        before = fonts.font("body").pixelSize()
        self.open_settings()
        self.pick(1)
        self.assertGreater(fonts.font("body").pixelSize(), before)

    def test_size_is_restored_at_the_next_sign_in(self):
        self.open_settings()
        self.pick(1)
        self.app.sign_out()
        self.settle()
        self.assertEqual(theme.text_size_name(), "normal")  # на экране входа обычный
        user = self.services.auth.login("nessquish", "demo12345")
        self.app.sign_in(user, "demo12345")
        self.settle()
        self.assertEqual(theme.text_size_name(), "medium")

    def test_broken_saved_value_falls_back_to_normal(self):
        self.app.preferences.set(self.app.user.id, "text_size", "gigantic")
        self.app.apply_user_changes(self.app.user, start=sections.HOME)
        self.settle()
        self.assertEqual(theme.text_size_name(), "normal")

    def test_every_screen_builds_at_the_largest_size(self):
        self.open_settings()
        self.pick(2)
        for name in sections.ALL:
            self.open(name)
        self.shell.edit_product(1)
        self.settle()
        self.shell.open_product(1)
        self.settle()


class SidebarCollapseTest(ShellTestCase):
    def collapse_button(self):
        return find_all(self.shell.sidebar, IconButton)[0]

    def test_sidebar_is_open_by_default(self):
        self.assertFalse(self.shell.sidebar_collapsed)
        self.assertTrue(self.shell.sidebar.isVisible())
        self.assertFalse(self.shell._rail.isVisible())

    def test_collapse_hides_the_sidebar_and_shows_the_rail(self):
        click(self.collapse_button())
        self.settle()
        self.assertTrue(self.shell.sidebar_collapsed)
        self.assertFalse(self.shell.sidebar.isVisible())
        self.assertTrue(self.shell._rail.isVisible())

    def test_rail_button_expands_it_back(self):
        self.shell.set_sidebar_collapsed(True)
        self.settle()
        click(find_all(self.shell._rail, IconButton)[0])
        self.settle()
        self.assertFalse(self.shell.sidebar_collapsed)
        self.assertTrue(self.shell.sidebar.isVisible())
        self.assertFalse(self.shell._rail.isVisible())

    def test_choice_is_remembered_and_restored(self):
        self.shell.set_sidebar_collapsed(True)
        self.assertTrue(self.app.preferences.get(self.app.user.id, "sidebar_collapsed"))
        self.app.apply_user_changes(self.app.user, start=sections.HOME)
        self.settle()
        self.assertTrue(self.shell.sidebar_collapsed)
        self.assertTrue(self.shell._rail.isVisible())

    def test_navigation_keeps_working_when_collapsed(self):
        self.shell.set_sidebar_collapsed(True)
        self.open(sections.HISTORY)
        self.assertEqual(self.shell.section, sections.HISTORY)


if __name__ == "__main__":
    unittest.main()
