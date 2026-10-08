"""Тесты переключения темы, тёмной палитры и построения экранов в тёмной теме."""

from pharmacy.ui import sections, theme
from pharmacy.ui.screens.settings import SettingsScreen
from tests.qt_helpers import ShellTestCase, click


class ThemeSwitchTest(ShellTestCase):
    def toggle(self):
        self.shell.toggle_theme()
        self.settle()

    def test_menu_offers_the_dark_theme(self):
        self.assertEqual(self.shell.sidebar.theme_link.text(), "Тёмная тема")

    def test_toggle_switches_to_dark_and_back(self):
        self.toggle()
        self.assertEqual(theme.theme_name(), "dark")
        self.assertEqual(self.app.user.theme, "dark")
        self.assertEqual(self.shell.sidebar.theme_link.text(), "Светлая тема")
        self.toggle()
        self.assertEqual(theme.theme_name(), "light")
        self.assertEqual(self.app.user.theme, "light")

    def test_menu_link_switches_the_theme(self):
        click(self.shell.sidebar.theme_link)
        self.settle()
        self.assertEqual(theme.theme_name(), "dark")

    def test_choice_is_saved_for_the_next_sign_in(self):
        self.toggle()
        saved = self.services.settings.get_user(self.app.user.id)
        self.assertEqual(saved.theme, "dark")

    def test_current_section_is_kept(self):
        self.open(sections.HISTORY)
        self.toggle()
        self.assertEqual(self.shell.section, sections.HISTORY)

    def test_colors_really_change(self):
        before = self.app.palette().window().color().name()
        self.toggle()
        after = self.app.palette().window().color().name()
        self.assertNotEqual(after, before)
        self.assertEqual(after.upper(), theme.DARK.bg.upper())

    def test_screen_is_painted_in_the_new_colors(self):
        self.toggle()
        pixel = self.app.grab().toImage().pixelColor(self.app.width() - 3, 3)
        self.assertEqual(pixel.name().upper(), theme.DARK.bg.upper())

    def test_other_settings_survive_the_switch(self):
        self.db.execute("UPDATE users SET warning_days = 12, notify_low_stock = 0")
        self.app.user = self.services.settings.get_user(self.app.user.id)
        self.shell.user = self.app.user
        self.toggle()
        saved = self.services.settings.get_user(self.app.user.id)
        self.assertEqual((saved.warning_days, saved.notify_low_stock), (12, False))

    def test_setting_the_same_theme_does_nothing(self):
        shell = self.shell
        shell.set_theme("light")
        self.settle()
        self.assertIs(self.app.screen_widget, shell)

    def test_settings_switch_applies_the_theme_at_once(self):
        self.open(sections.SETTINGS)
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


class DarkPaletteScreenshotTest(ShellTestCase):
    def test_dark_cards_use_the_dark_card_color(self):
        self.shell.toggle_theme()
        self.settle()
        card = self.page.stat_cards[0]
        image = card.grab().toImage()
        center = image.pixelColor(card.width() // 2, card.height() // 2)
        self.assertEqual(center.name().upper(), theme.DARK.card.upper())


class SystemThemeTest(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        from pharmacy.ui import runtime

        self.system = "dark"
        original = runtime.system_theme
        runtime.system_theme = lambda: self.system
        self.addCleanup(setattr, runtime, "system_theme", original)

    def choose_system(self):
        self.shell.set_theme("system")
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
