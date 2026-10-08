"""Тесты экрана списка покупок и окна добавления."""

from typing import List

from PySide6.QtWidgets import QLabel

from pharmacy.ui import sections
from pharmacy.ui.screens.product_card import ProductCardDialog
from pharmacy.ui.screens.shopping import AddItemDialog, ShoppingScreen
from pharmacy.ui.widgets.combo import ComboField
from pharmacy.ui.widgets.controls import Checkbox
from tests.qt_helpers import ShellTestCase, click, find_all


class ShoppingTestCase(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.open(sections.SHOPPING)

    @property
    def shopping(self) -> ShoppingScreen:
        return self.page

    def names(self) -> List[str]:
        return [row[1] for row in self.shopping.table.row_texts]

    def boxes(self) -> List[Checkbox]:
        return self.shopping.table.cell_widgets(0)

    def items(self, bought=None):
        return self.services.shopping.list_items(self.app.user.id, bought)

    def pick(self, index: int) -> None:
        """Отмечает флажок в строке так, как это делает нажатие мышью."""
        click(self.boxes()[index])
        self.settle()


class ShoppingScreenTest(ShoppingTestCase):
    def test_lists_all_items_open_first(self):
        self.assertEqual(len(self.names()), 4)
        self.assertEqual(self.names()[-1], "Витамин C")

    def test_tab_labels_show_counts(self):
        self.assertEqual(
            self.shopping._tab_labels(), ["Все · 4", "Не куплено · 3", "Куплено · 1"]
        )

    def test_tabs_filter_the_list(self):
        self.shopping._on_tab(1)
        self.assertEqual(len(self.names()), 3)
        self.assertNotIn("Витамин C", self.names())
        self.shopping._on_tab(2)
        self.assertEqual(self.names(), ["Витамин C"])

    def test_clicking_a_tab_filters(self):
        tabs = self.shopping.tabs
        left, right = tabs.spans[2]
        click(tabs, (left + right) // 2, tabs.height() // 2)
        self.settle()
        self.assertEqual(self.names(), ["Витамин C"])

    def test_table_cells(self):
        rows = {row[1]: row for row in self.shopping.table.row_texts}
        self.assertEqual(rows["Бинт"][2], "2 шт.")
        self.assertEqual(rows["Бинт"][3], "Уведомление")
        self.assertEqual(rows["Пластыри"][3], "Вручную")
        self.assertRegex(rows["Бинт"][5], r"\d\d\.\d\d\.\d{4}")

    def test_bought_item_has_the_green_badge(self):
        rows = {row[1]: row for row in self.shopping.table.row_texts}
        self.assertEqual(rows["Витамин C"][4], "Куплено")
        self.assertEqual(rows["Бинт"][4], "Не куплено")

    def test_bar_is_hidden_without_selection(self):
        self.assertFalse(self.shopping.bar.isVisible())

    def test_selecting_rows_shows_bar_with_count(self):
        self.pick(0)
        self.pick(1)
        self.assertTrue(self.shopping.bar.isVisible())
        self.assertEqual(self.shopping.bar.text, "Выбрано: 2")

    def test_unselecting_hides_bar(self):
        self.pick(0)
        self.pick(0)
        self.assertFalse(self.shopping.bar.isVisible())

    def test_select_all(self):
        self.shopping._toggle_all(True)
        self.settle()
        self.assertEqual(self.shopping.bar.text, "Выбрано: 4")
        self.assertTrue(self.shopping.select_all.value)
        self.shopping._toggle_all(False)
        self.assertEqual(self.shopping.selected, set())

    def test_header_checkbox_selects_everything(self):
        click(self.shopping.select_all)
        self.settle()
        self.assertEqual(len(self.shopping.selected), 4)

    def test_selection_is_cleared_when_tab_changes(self):
        self.pick(0)
        self.shopping._on_tab(2)
        self.assertEqual(self.shopping.selected, set())

    def test_mark_bought(self):
        self.pick(0)
        self.pick(1)
        self.buttons("Отметить как купленные")[0].invoke()
        self.settle()
        self.assertEqual(len(self.items(bought=True)), 3)
        self.assertEqual(self.shopping.selected, set())
        self.assertFalse(self.shopping.bar.isVisible())

    def test_remove_selected(self):
        self.pick(2)
        self.buttons("Удалить из списка")[0].invoke()
        self.settle()
        self.assertEqual(len(self.items()), 3)
        self.assertEqual(len(self.names()), 3)

    def test_selected_row_is_highlighted_and_header_loses_rounding(self):
        self.pick(0)
        self.assertEqual(self.shopping.table._grid_host.paint_header, True)
        self.pick(0)
        self.assertEqual(self.shopping.table._grid_host.paint_header, False)

    def test_linked_item_opens_the_product_card(self):
        first = self.shopping.table.cell_widgets(1)[0]
        click(first)
        self.settle()
        self.assertEqual(len(find_all(self.app, ProductCardDialog)), 1)
        self.assertIsInstance(self.page, ShoppingScreen)

    def test_empty_list_message(self):
        self.db.execute("DELETE FROM shopping_list")
        self.open(sections.SHOPPING)
        texts = [w.text() for w in find_all(self.page, QLabel)]
        self.assertTrue(any("Список покупок пуст" in t for t in texts))


class AddItemDialogTest(ShoppingTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.dialog = AddItemDialog(
            self.app, self.services, self.app.user.id, self.shopping._reload
        )
        self.settle()

    def test_button_opens_the_dialog(self):
        self.dialog.close_modal()
        self.settle()
        self.assertEqual(find_all(self.app, ComboField), [])
        self.buttons("Добавить вручную")[0].invoke()
        self.settle()
        self.assertEqual(len(find_all(self.app, ComboField)), 1)

    def test_defaults(self):
        self.assertEqual(self.dialog.quantity.get(), "1")
        self.assertEqual(self.dialog.unit.get(), "шт.")
        self.assertEqual(self.dialog.name.get(), "")

    def test_adds_manual_item_and_refreshes_list(self):
        self.dialog.name.set("Перекись водорода")
        self.dialog.quantity.set("2")
        self.dialog._submit()
        self.settle()
        self.assertIn("Перекись водорода", self.names())
        item = next(i for i in self.items() if i.name == "Перекись водорода")
        self.assertEqual((item.quantity, item.unit), (2, "шт."))
        self.assertEqual(find_all(self.app, ComboField), [])

    def test_empty_name_is_marked(self):
        self.dialog._submit()
        self.assertEqual(self.dialog.name.error, "Введите название")
        self.assertEqual(len(self.items()), 4)

    def test_bad_quantity_is_marked(self):
        self.dialog.name.set("Вата")
        self.dialog.quantity.set("0")
        self.dialog._submit()
        self.assertIsNotNone(self.dialog.quantity.error)

    def test_cancel_closes_without_adding(self):
        self.buttons("Отмена")[0].invoke()
        self.settle()
        self.assertEqual(find_all(self.app, ComboField), [])
        self.assertEqual(len(self.items()), 4)

    def test_choice_from_list_fills_the_name(self):
        field = self.dialog.name
        field._pick("Ибупрофен")
        self.assertEqual(field.get(), "Ибупрофен")

    def test_choices_are_products_of_the_kit(self):
        self.assertIn("Ибупрофен", self.dialog.name._choices)
        self.assertEqual(len(self.dialog.name._choices), 8)

    def test_arrow_opens_the_list(self):
        field = self.dialog.name
        click(field._trailing)
        self.settle()
        self.assertIsNotNone(field.popup)
        self.assertTrue(field.popup.isVisible())
        field.popup.close_list()
        self.assertIsNone(field.popup)

    def test_list_picks_fill_the_field(self):
        field = self.dialog.name
        field.toggle_list()
        self.settle()
        field.popup._on_pick("Бинт")
        self.assertEqual(field.get(), "Бинт")


class LiveSearchTest(ShoppingTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.dialog = AddItemDialog(
            self.app, self.services, self.app.user.id, self.shopping._reload
        )
        self.settle()
        self.field = self.dialog.name

    def test_suggestions_follow_every_letter(self):
        self.field.set("и")
        self.field._refresh_suggestions()
        wide = len(self.field.popup.options)
        self.field.set("ибуп")
        self.field._refresh_suggestions()
        self.assertTrue(self.field.popup.isVisible())
        self.assertTrue(0 < len(self.field.popup.options) <= wide)
        self.assertTrue(
            all("ибуп" in text.casefold() for _, text in self.field.popup.options)
        )

    def test_no_match_closes_the_list(self):
        self.field.set("ибуп")
        self.field._refresh_suggestions()
        self.field.set("яяяя")
        self.field._refresh_suggestions()
        self.assertIsNone(self.field.popup)

    def test_chosen_product_gives_a_card_link(self):
        self.field.set("ибуп")
        self.field._refresh_suggestions()
        number = self.field.popup.options[0][0]
        self.field.popup._on_pick(number)
        self.assertEqual(self.field.product_id, number)
        self.dialog._submit()
        item = next(i for i in self.items() if i.product_id == number)
        self.assertEqual(item.name, self.field.get())

    def test_editing_the_name_drops_the_link(self):
        self.field.set("ибуп")
        self.field._refresh_suggestions()
        self.field.popup._on_pick(self.field.popup.options[0][0])
        self.field.set(self.field.get() + " детский")
        self.assertIsNone(self.field.product_id)

    def test_typing_opens_suggestions_without_losing_focus(self):
        from tests.qt_helpers import type_text

        type_text(self.field.entry, "ибуп")
        self.settle()
        self.assertIsNotNone(self.field.popup)
        self.assertTrue(self.field.popup.isVisible())
