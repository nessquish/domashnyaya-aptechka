"""Тесты: рядом с каждым числом в интерфейсе стоит единица измерения."""

import re

from PySide6.QtWidgets import QLabel

from pharmacy.ui import sections
from pharmacy.ui.screens.product_card import ProductCardDialog
from pharmacy.ui.screens.product_form import ProductFormDialog, show_units
from pharmacy.utils.units import UNITS
from tests.qt_helpers import ShellTestCase, find_all

UNIT_PATTERN = "|".join(re.escape(unit) for unit in UNITS)
# Число, за которым не идёт единица (числа в датах и счётчиках не считаются).
BARE_AMOUNT = re.compile(
    rf"(?<![\d.:])\d+([.,]\d+)?(?! ?({UNIT_PATTERN})(?!\w))(?![\d.:])"
)


class UnitsEverywhereTest(ShellTestCase):
    def texts(self, widget):
        return [w.text() for w in find_all(widget, QLabel)]

    def product_id(self, name):
        views = self.services.products.list_products(self.app.user.id)
        return next(v.product.id for v in views if v.product.name == name)

    def test_kit_table_has_a_unit_in_every_row(self):
        kit = self.open(sections.MY_KIT)
        for row in kit.table.row_texts:
            self.assertIn(row[4], UNITS, row)  # столбец «Ед. изм.»
            self.assertTrue(row[3], row)  # и число рядом

    def test_product_card_quantity_and_minimum_have_units(self):
        self.shell.open_product(self.product_id("Ибупрофен"))
        self.settle()
        texts = self.texts(find_all(self.app, ProductCardDialog)[0])
        self.assertIn("2 упак.", texts)
        self.assertIn("3 упак.", texts)

    def test_shopping_table_quantity_has_a_unit(self):
        page = self.open(sections.SHOPPING)
        for row in page.table.row_texts:
            self.assertRegex(row[3], rf"^\d+([.,]\d+)? ({UNIT_PATTERN})$", row)

    def test_dashboard_remaining_text_has_units(self):
        texts = self.texts(self.page)
        remaining = [t for t in texts if t.startswith("Осталось")]
        self.assertTrue(remaining)
        for text in remaining:
            self.assertRegex(text, rf"Осталось \d+\S* ({UNIT_PATTERN}) · минимум")
            self.assertRegex(text, rf"минимум \d+\S* ({UNIT_PATTERN})$")

    def test_notifications_messages_have_units(self):
        page = self.open(sections.NOTIFICATIONS)
        low = [t for t in self.texts(page) if "осталось" in t and "минимум" in t]
        self.assertTrue(low)
        for text in low:
            self.assertRegex(
                text, rf"осталось \S+ ({UNIT_PATTERN}) \(минимум \S+ ({UNIT_PATTERN})\)"
            )

    def test_history_of_quantity_change_has_units(self):
        self.shell.edit_product(self.product_id("Ибупрофен"))
        self.settle()
        dialog = find_all(self.app, ProductFormDialog)[0]
        dialog.fields["quantity"].set("10")
        dialog.fields["min_quantity"].set("4")
        dialog._submit()
        self.settle()
        page = self.open(sections.HISTORY)
        descriptions = " ".join(self.texts(page))
        self.assertIn("количество изменено с 2 упак. до 10 упак.", descriptions)
        self.assertIn("минимальный остаток изменён с 3 упак. до 4 упак.", descriptions)

    def test_history_has_no_bare_amounts(self):
        page = self.open(sections.HISTORY)
        for text in self.texts(page):
            if "количество изменено" in text or "остаток изменён" in text:
                self.assertIsNone(BARE_AMOUNT.search(text), text)


class FormUnitLabelsTest(ShellTestCase):
    def open_dialog(self):
        self.shell.add_product()
        self.settle()
        from pharmacy.ui.screens.product_form import ProductFormDialog

        return find_all(self.app, ProductFormDialog)[0]

    def test_unit_is_a_dropdown_with_the_fixed_list(self):
        dialog = self.open_dialog()
        select = dialog.fields["unit"]
        self.assertEqual([value for value, _ in select.choices], list(UNITS))

    def test_default_unit_is_pieces(self):
        dialog = self.open_dialog()
        self.assertEqual(dialog.fields["unit"].get(), "шт.")

    def test_labels_of_numbers_name_the_unit(self):
        dialog = self.open_dialog()
        self.assertEqual(dialog.fields["quantity"].title, "Количество (шт.)")
        self.assertEqual(
            dialog.fields["min_quantity"].title, "Минимальный остаток (шт.)"
        )

    def test_labels_follow_the_chosen_unit(self):
        dialog = self.open_dialog()
        dialog.fields["unit"]._pick("мл")
        self.assertEqual(dialog.fields["quantity"].title, "Количество (мл)")
        self.assertEqual(
            dialog.fields["min_quantity"].title, "Минимальный остаток (мл)"
        )
        dialog.fields["unit"]._pick("табл.")
        self.assertEqual(dialog.fields["quantity"].title, "Количество (табл.)")

    def test_edit_form_shows_the_unit_of_the_product(self):
        views = self.services.products.list_products(self.app.user.id)
        target = next(v for v in views if v.product.name == "Хлоргексидин")
        self.shell.edit_product(target.product.id)
        self.settle()
        dialog = find_all(self.app, ProductFormDialog)[0]
        self.assertEqual(dialog.fields["quantity"].title, "Количество (фл.)")

    def test_saved_product_uses_the_selected_unit(self):
        dialog = self.open_dialog()
        dialog.fields["name"].set("Амоксициллин")
        dialog.fields["quantity"].set("500")
        dialog.fields["unit"]._pick("мг")
        dialog.save_button.invoke()
        added = self.services.products.list_products(self.app.user.id, search="амокси")
        self.assertEqual(added[0].product.unit, "мг")

    def test_product_saved_without_choosing_gets_pieces(self):
        dialog = self.open_dialog()
        dialog.fields["name"].set("Лейкопластырь")
        dialog.fields["quantity"].set("5")
        dialog.save_button.invoke()
        added = self.services.products.list_products(self.app.user.id, search="лейко")
        self.assertEqual(added[0].product.unit, "шт.")

    def test_show_units_falls_back_to_pieces_without_a_choice(self):
        dialog = self.open_dialog()
        dialog.fields["unit"].set(None)
        show_units(dialog.fields)
        self.assertEqual(dialog.fields["quantity"].title, "Количество (шт.)")

    def test_manual_shopping_unit_is_a_dropdown_with_pieces_by_default(self):
        from pharmacy.ui.screens.shopping import AddItemDialog

        self.open(sections.SHOPPING)
        dialog = AddItemDialog(self.app, self.services, self.app.user.id, lambda: None)
        self.assertEqual(dialog.unit.get(), "шт.")
        self.assertEqual([value for value, _ in dialog.unit.choices], list(UNITS))
