"""Тесты переключения темы, тёмной палитры и построения экранов в тёмной теме."""

from pharmacy.ui import sections, theme
from pharmacy.ui.screens.settings import SettingsScreen
from tests.qt_helpers import ShellTestCase, click


class ThemeSwitchTest(ShellTestCase):
    def toggle(self):
        self.shell.toggle_theme()
        self.settle()

    def test_toggle_switches_to_dark_and_back(self):
        self.toggle()
        self.assertEqual(theme.theme_name(), "dark")
        self.assertEqual(self.app.theme_mode(self.app.user), "dark")
        self.assertEqual(self.shell.sidebar.theme_link.text(), "Светлая тема")
        self.toggle()
        self.assertEqual(theme.theme_name(), "light")
        self.assertEqual(self.app.theme_mode(self.app.user), "light")

    def test_choice_is_saved_for_the_next_sign_in(self):
        self.toggle()
        # Выбор темы хранится для устройства и действует и при следующем входе.
        self.assertEqual(self.app.preferences.get(0, "theme_mode"), "dark")
        self.assertEqual(self.app.theme_mode(self.app.user), "dark")

    def test_current_section_is_kept(self):
        self.open(sections.HISTORY)
        self.toggle()
        self.assertEqual(self.shell.section, sections.HISTORY)

    def test_settings_switch_applies_the_theme_at_once(self):
        self.open(sections.SETTINGS)
        self.page.open_section("appearance")
        switch = self.page.theme_switch
        left, right = switch.spans[1]
        click(switch, (left + right) // 2, 10)
        self.settle()
        self.assertEqual(theme.theme_name(), "dark")
        self.assertIsInstance(self.page, SettingsScreen)

    def test_every_screen_builds_in_the_dark_theme(self):
        self.toggle()
        for name in sections.ALL:
            self.open(name)
        self.shell.edit_product(1)
        self.settle()
        self.shell.open_product(1)
        self.settle()


class SystemThemeTest(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        from pharmacy.ui import runtime

        self.system = "dark"
        original = runtime.system_theme
        runtime.system_theme = lambda: self.system
        self.addCleanup(setattr, runtime, "system_theme", original)

    def choose_system(self):
        self.shell.set_theme("light")  # выбор по умолчанию уже «системная»
        self.settle()
        self.app.screen_widget.set_theme("system")
        self.settle()

    def test_system_choice_follows_the_system(self):
        self.choose_system()
        self.assertEqual(theme.theme_name(), "dark")
        self.assertEqual(self.app.theme_mode(self.app.user), "system")

    def test_system_change_is_picked_up(self):
        self.choose_system()
        self.system = "light"
        self.app._follow_system_theme()
        self.settle()
        self.assertEqual(theme.theme_name(), "light")
        self.assertEqual(self.app.theme_mode(self.app.user), "system")

    def test_fixed_choice_ignores_the_system(self):
        self.shell.set_theme("light")
        self.settle()
        self.app._follow_system_theme()
        self.assertEqual(theme.theme_name(), "light")

    def test_login_screen_follows_the_system(self):
        self.app.sign_out()
        self.settle()
        self.assertEqual(theme.theme_name(), "dark")
        self.system = "light"
        self.app._follow_system_theme()
        self.settle()
        self.assertEqual(theme.theme_name(), "light")
