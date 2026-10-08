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

    def test_keys_do_not_overwrite_each_other(self):
        prefs = Preferences(self.path())
        prefs.set(1, "text_size", "large")
        prefs.set(1, "sidebar_collapsed", True)
        self.assertEqual(prefs.get(1, "text_size"), "large")
        self.assertTrue(prefs.get(1, "sidebar_collapsed"))

    def test_in_memory_mode_writes_nothing(self):
        prefs = Preferences()
        prefs.set(1, "text_size", "large")
        self.assertEqual(prefs.get(1, "text_size"), "large")

    def test_broken_file_is_ignored(self):
        path = self.path()
        path.write_text("{не json", encoding="utf-8")
        prefs = Preferences(path)
        self.assertEqual(prefs.get(1, "text_size", "normal"), "normal")
        prefs.set(1, "text_size", "large")  # и после этого всё работает
        self.assertEqual(Preferences(path).get(1, "text_size"), "large")

    def test_unexpected_json_shape_is_ignored(self):
        path = self.path()
        path.write_text(json.dumps(["не", "словарь"]), encoding="utf-8")
        self.assertIsNone(Preferences(path).get(1, "text_size"))
        path.write_text(json.dumps({"1": "строка"}), encoding="utf-8")
        self.assertIsNone(Preferences(path).get(1, "text_size"))

    def test_creates_missing_folder(self):
        path = self.path().parent / "nested" / "p.json"
        Preferences(path).set(1, "k", 1)
        self.assertTrue(path.is_file())


class TextScaleTest(unittest.TestCase):
    def tearDown(self):
        theme.set_text_size("normal")

    def test_sizes_for_the_main_text(self):
        results = {}
        for name in ("normal", "medium", "large"):
            theme.set_text_size(name)
            results[name] = theme.scaled(12)
        self.assertEqual(results, {"normal": 13, "medium": 15, "large": 17})

    def test_each_step_is_clearly_visible(self):
        """Соседние размеры отличаются не меньше чем на 2 пикселя у основного текста."""
        theme.set_text_size("normal")
        normal = theme.scaled(12)
        theme.set_text_size("medium")
        medium = theme.scaled(12)
        theme.set_text_size("large")
        large = theme.scaled(12)
        self.assertGreaterEqual(medium - normal, 2)
        self.assertGreaterEqual(large - medium, 2)

    def test_smallest_text_is_not_tiny(self):
        for name in theme.TEXT_SIZES:
            theme.set_text_size(name)
            smallest = min(theme.scaled(size) for size, _w in theme.TYPOGRAPHY.values())
            self.assertGreaterEqual(smallest, 12, name)

    def test_every_style_gets_bigger_with_each_step(self):
        for style, (size, _weight) in theme.TYPOGRAPHY.items():
            theme.set_text_size("normal")
            normal = theme.scaled(size)
            theme.set_text_size("medium")
            medium = theme.scaled(size)
            theme.set_text_size("large")
            large = theme.scaled(size)
            self.assertLess(normal, medium, style)
            self.assertLess(medium, large, style)

    def test_unknown_size_is_rejected(self):
        with self.assertRaises(ValueError):
            theme.set_text_size("huge")
        self.assertEqual(theme.text_size_name(), "normal")

    def test_font_follows_the_size(self):
        theme.set_text_size("normal")
        normal = fonts.font("body").pixelSize()
        theme.set_text_size("large")
        self.assertEqual(fonts.font("body").pixelSize(), theme.scaled(12))
        self.assertGreater(fonts.font("body").pixelSize(), normal)

    def test_window_and_sidebar_grow_with_text(self):
        widths = []
        for name in ("normal", "medium", "large"):
            theme.set_text_size(name)
            widths.append((theme.window_width(), theme.sidebar_width()))
        for smaller, bigger in zip(widths, widths[1:]):
            self.assertGreater(bigger[0], smaller[0])
            self.assertGreater(bigger[1], smaller[1])
        # Даже при обычном тексте панель шире, чем в макете: текст стал крупнее.
        self.assertGreater(widths[0][1], theme.SIDEBAR_WIDTH)

    def test_scale_is_exposed(self):
        theme.set_text_size("medium")
        self.assertEqual(theme.text_scale(), 1.25)

    def test_text_gets_wider_with_the_size(self):
        theme.set_text_size("normal")
        normal = fonts.text_width("Список покупок", "body")
        theme.set_text_size("large")
        self.assertGreater(fonts.text_width("Список покупок", "body"), normal)


class FontsTest(unittest.TestCase):
    def test_inter_is_registered_from_the_bundled_files(self):
        self.assertTrue(fonts.register_fonts())
        self.assertEqual(fonts.font("body").family(), "Inter")

    def test_every_weight_comes_from_inter_not_the_fallback(self):
        for style, (_size, weight) in theme.TYPOGRAPHY.items():
            font = fonts.font(style)
            self.assertEqual(font.family(), "Inter", style)
            self.assertEqual(int(font.weight()), weight, style)

    def test_installed_inter_has_all_five_files(self):
        from PySide6.QtGui import QFontDatabase

        self.assertEqual(
            QFontDatabase.styles("Inter"),
            ["Regular", "Medium", "SemiBold", "Bold", "ExtraBold"],
        )

    def test_every_style_has_a_font(self):
        for style in theme.TYPOGRAPHY:
            self.assertGreater(fonts.font(style).pixelSize(), 0, style)
            self.assertGreater(fonts.line_height(style), 0, style)

    def test_missing_files_fall_back_gracefully(self):
        with mock.patch.object(fonts, "FONTS_DIR", Path("нет/такой/папки")):
            self.assertFalse(fonts.register_fonts())
        fonts.register_fonts()


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

    def test_window_never_exceeds_the_screen(self):
        with mock.patch.object(runtime, "screen_size", return_value=(1280, 800)):
            self.open_settings()
            self.pick(2)
            self.assertLessEqual(self.app.minimumWidth(), 1280 - 40)

    def test_text_really_gets_bigger(self):
        before = fonts.font("body").pixelSize()
        self.open_settings()
        self.pick(1)
        self.assertGreater(fonts.font("body").pixelSize(), before)

    def test_selecting_the_same_size_does_nothing(self):
        self.open_settings()
        shell = self.shell
        shell.set_text_size("normal")
        self.assertIs(self.app.screen_widget, shell)

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

    def test_content_gets_the_freed_space(self):
        before = self.shell._scroll.width()
        self.shell.set_sidebar_collapsed(True)
        self.settle()
        self.assertGreater(self.shell._scroll.width(), before + 100)

    def test_choice_is_remembered_and_restored(self):
        self.shell.set_sidebar_collapsed(True)
        self.assertTrue(self.app.preferences.get(self.app.user.id, "sidebar_collapsed"))
        self.app.apply_user_changes(self.app.user, start=sections.HOME)
        self.settle()
        self.assertTrue(self.shell.sidebar_collapsed)
        self.assertTrue(self.shell._rail.isVisible())

    def test_collapsing_twice_changes_nothing(self):
        self.shell.set_sidebar_collapsed(True)
        self.shell.set_sidebar_collapsed(True)
        self.settle()
        self.assertTrue(self.shell._rail.isVisible())

    def test_navigation_keeps_working_when_collapsed(self):
        self.shell.set_sidebar_collapsed(True)
        self.open(sections.HISTORY)
        self.assertEqual(self.shell.section, sections.HISTORY)

    def test_other_users_keep_their_own_state(self):
        self.shell.set_sidebar_collapsed(True)
        self.assertFalse(self.app.preferences.get(999, "sidebar_collapsed", False))


if __name__ == "__main__":
    unittest.main()
