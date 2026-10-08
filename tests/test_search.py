"""Поиск по программе: товары, разделы и настройки, переход к найденному."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from pharmacy.ui import sections
from pharmacy.ui.screens.my_kit import MyKitScreen
from pharmacy.ui.screens.search import EMPTY_TEXT, SearchModal
from pharmacy.ui.search_index import (
    MAX_RESULTS,
    PRODUCT,
    SEARCH_INDEX,
    SECTION,
    SETTINGS,
    Target,
    search_sections,
)
from tests.helpers import DatabaseTestCase
from tests.qt_helpers import ShellTestCase, click, type_text


class ProductSearchTest(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        from pharmacy.services.container import build_services

        self.service = build_services(self.db).products
        self.user_id = self.add_user("anna")
        self.add_product(self.user_id, name="Парацетамол")
        self.add_product(self.user_id, name="Ибупрофен")
        self.add_product(self.user_id, name="Детский парацетамол сироп")
        other = self.add_user("boris")
        self.add_product(other, name="Парацетамол чужой")

    def names(self, query, limit=10):
        return [
            p.name for p in self.service.search_products(self.user_id, query, limit)
        ]

    def test_finds_by_name_ignoring_case_and_prefers_the_start(self):
        self.assertEqual(
            self.names("ПАРАЦЕТ"), ["Парацетамол", "Детский парацетамол сироп"]
        )

    def test_finds_by_category(self):
        self.assertEqual(len(self.names("лекарства")), 3)

    def test_finds_by_note(self):
        self.db.execute(
            "UPDATE products SET note = ? WHERE name = ?", ("Для ребёнка", "Ибупрофен")
        )
        self.assertEqual(self.names("ребён"), ["Ибупрофен"])

    def test_limit_empty_query_and_other_users(self):
        self.assertEqual(len(self.names("а", limit=2)), 2)
        self.assertEqual(self.names("   "), [])
        self.assertNotIn("Парацетамол чужой", self.names("парацетамол"))


class IndexTest(DatabaseTestCase):
    def test_theme_leads_to_appearance_settings(self):
        entry = search_sections("тема")[0]
        self.assertEqual(entry.title, "Тема")
        self.assertEqual(entry.path, "Настройки → Внешний вид → Тема")
        self.assertEqual(entry.target, Target(SETTINGS, "appearance"))

    def test_keywords_work(self):
        self.assertEqual(search_sections("excel")[0].title, "Экспорт данных")
        self.assertEqual(search_sections("github")[0].target.value, "about")

    def test_sections_are_found(self):
        entry = search_sections("покуп")[0]
        self.assertEqual(entry.target, Target(SECTION, sections.SHOPPING))

    def test_title_match_goes_before_keyword_match(self):
        titles = [e.title for e in search_sections("истор")]
        self.assertEqual(titles[0], "История")

    def test_limit_and_nothing_found(self):
        self.assertLessEqual(len(search_sections("а")), MAX_RESULTS)
        self.assertEqual(search_sections("яяяяяя"), [])
        self.assertEqual(search_sections(""), [])

    def test_every_target_points_to_a_real_place(self):
        from pharmacy.ui.screens.settings import SECTIONS

        keys = {key for key, _title, _icon in SECTIONS}
        for entry in SEARCH_INDEX:
            if entry.target.kind == SETTINGS:
                self.assertIn(entry.target.value, keys, entry.title)
            else:
                self.assertIn(entry.target.value, sections.ALL, entry.title)


class SearchWindowTest(ShellTestCase):
    def open_search(self) -> SearchModal:
        self.app.open_search()
        self.settle()
        return self.app.search_modal

    def type(self, modal, text):
        modal.field.set(text)
        modal._update()
        self.settle()

    def test_magnifier_opens_the_window(self):
        click(self.shell.sidebar.search_button)
        self.settle()
        self.assertTrue(self.app.search_modal.is_open)

    def test_ctrl_f_opens_it_once(self):
        QTest.keyClick(self.app, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        self.settle()
        first = self.app.search_modal
        self.assertTrue(first.is_open)
        self.app.open_search()
        self.assertIs(self.app.search_modal, first)

    def test_not_available_before_sign_in(self):
        self.app.sign_out()
        self.settle()
        self.app.open_search()
        self.assertFalse(
            self.app.search_modal is not None and self.app.search_modal.is_open
        )

    def test_shortcuts_are_registered(self):
        from PySide6.QtGui import QShortcut

        keys = {s.key().toString() for s in self.app.findChildren(QShortcut)}
        self.assertIn(QKeySequence("Ctrl+F").toString(), keys)

    def test_results_are_grouped_and_limited(self):
        modal = self.open_search()
        self.type(modal, "а")
        self.assertTrue(modal.rows)
        kinds = [row.target.kind for row in modal.rows]
        self.assertLessEqual(kinds.count(PRODUCT), MAX_RESULTS)
        self.assertLessEqual(len(kinds) - kinds.count(PRODUCT), MAX_RESULTS)
        self.assertEqual(kinds, sorted(kinds, key=lambda k: k != PRODUCT))

    def test_nothing_found_message(self):
        modal = self.open_search()
        self.type(modal, "яяяяяя")
        self.assertEqual(modal.rows, [])
        self.assertEqual(modal.message.text(), EMPTY_TEXT)
        self.assertEqual(EMPTY_TEXT, "Ничего не найдено")

    def test_typing_updates_results_without_enter(self):
        modal = self.open_search()
        type_text(modal.field.entry, "парац")
        self.settle()
        self.assertEqual(modal.rows[0].title, "Парацетамол")

    def test_product_result_opens_the_kit_with_the_row_highlighted(self):
        modal = self.open_search()
        self.type(modal, "парацетамол")
        click(modal.rows[0])
        self.settle()
        self.assertFalse(modal.is_open)
        self.assertEqual(self.shell.section, sections.MY_KIT)
        kit = self.page
        self.assertIsInstance(kit, MyKitScreen)
        row = kit._shown_ids.index(modal.rows[0].target.value)
        self.assertIn(row, kit._table._fills)
        self.assertEqual(kit.selected, set())

    def test_search_filters_are_dropped_to_show_the_product(self):
        kit = self.open(sections.MY_KIT)
        kit._search = "бинт"
        kit._reload()
        self.assertEqual(len(kit._shown_ids), 1)
        product = next(
            p
            for p in self.services.products.search_products(
                self.app.user.id, "парацетамол"
            )
        )
        kit.reveal(product.id)
        self.assertIn(product.id, kit._shown_ids)

    def test_highlight_goes_away(self):
        modal = self.open_search()
        self.type(modal, "парацетамол")
        modal.open_active()
        self.settle()
        kit = self.page
        kit._clear_flash()
        self.assertEqual(kit._table._fills, {})

    def test_setting_result_opens_that_settings_section(self):
        modal = self.open_search()
        self.type(modal, "тема")
        settings_row = next(r for r in modal.rows if r.target.kind == SETTINGS)
        click(settings_row)
        self.settle()
        self.assertEqual(self.shell.section, sections.SETTINGS)
        self.assertEqual(self.page.section, "appearance")

    def test_section_result_navigates(self):
        modal = self.open_search()
        self.type(modal, "история")
        click(modal.rows[0])
        self.settle()
        self.assertEqual(self.shell.section, sections.HISTORY)

    def test_enter_opens_the_first_result_and_arrows_move(self):
        modal = self.open_search()
        self.type(modal, "а")
        self.assertEqual(modal.active_index, 0)
        QTest.keyClick(modal.field.entry, Qt.Key.Key_Down)
        self.assertEqual(modal.active_index, 1)
        QTest.keyClick(modal.field.entry, Qt.Key.Key_Up)
        self.assertEqual(modal.active_index, 0)
        target = modal.rows[0].target
        modal.open_active()
        self.settle()
        self.assertFalse(modal.is_open)
        self.assertIsNotNone(target)

    def test_escape_closes_without_moving(self):
        modal = self.open_search()
        modal.close_modal()
        self.settle()
        self.assertEqual(self.shell.section, sections.HOME)
