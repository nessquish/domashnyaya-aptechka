"""Порог низкого остатка, подписи количества, дата добавления, прокрутка списков."""

from pharmacy.services.notification_service import NotifyOptions
from pharmacy.services.status import ProductStatus
from pharmacy.ui import paging, sections, sorting
from pharmacy.ui.screens.shopping import AddItemDialog
from pharmacy.utils.textmatch import name_matches
from tests.qt_helpers import ShellTestCase


class TextMatchTest(ShellTestCase):
    def test_word_forms_and_case(self):
        self.assertTrue(name_matches("Витамин D", "витамины"))
        self.assertTrue(name_matches("Парацетамол", "ПАРАЦЕТАМОЛА"))
        self.assertTrue(name_matches("Ибупрофен", "ибу"))
        self.assertTrue(name_matches("Средство для посуды", "посуда"))
        self.assertTrue(name_matches("Ёлочная гирлянда", "елочная"))
        self.assertTrue(name_matches("Комплексный поливитаминный препарат", "витамины"))

    def test_unrelated_words_do_not_match(self):
        self.assertFalse(name_matches("Бинт", "бантик"))
        self.assertFalse(name_matches("Срок годности истёк", "история"))
        self.assertFalse(name_matches("Бинт", ""))


class LowStockThresholdTest(ShellTestCase):
    def set_threshold(self, value):
        self.app.preferences.set(self.app.user.id, "low_threshold", value)
        self.services.notifications.refresh(self.app.user.id)

    def low(self):
        views = self.services.products.list_products(
            self.app.user.id, status=ProductStatus.LOW_STOCK
        )
        return {v.product.name: v.product.quantity for v in views}

    def test_without_a_threshold_the_minimum_of_each_product_is_used(self):
        self.assertIn("Бинт", self.low())
        self.assertNotIn("Парацетамол", self.low())

    def test_threshold_is_applied_from_zero_up_to_it_inclusive(self):
        self.set_threshold(2)
        low = self.low()
        self.assertTrue(low)
        self.assertTrue(all(0 <= q <= 2 for q in low.values()))
        self.assertIn("Ибупрофен", low)  # количество 2 входит

    def test_bigger_threshold_shows_more(self):
        self.set_threshold(50)
        self.assertIn("Парацетамол", self.low())
        self.assertEqual(len(self.low()), 8)

    def test_kit_filter_and_dashboard_follow_it(self):
        self.set_threshold(3)
        kit = self.open(sections.MY_KIT)
        kit._on_status(ProductStatus.LOW_STOCK)
        names = {row[0] for row in kit.table.row_texts}
        self.assertEqual(names, set(self.low()))
        summary = self.services.dashboard.summary(self.app.user.id)
        self.assertEqual(summary.low_stock, len(self.low()))

    def test_notifications_use_the_same_threshold(self):
        self.set_threshold(3)
        count = len(
            [
                n
                for n in self.services.notifications.list_notifications(
                    self.app.user.id
                )
                if n.kind == "low_stock"
            ]
        )
        self.assertEqual(count, len(self.low()))

    def test_options_default(self):
        self.assertEqual(NotifyOptions().low_threshold, 0)


class QuantityCaptionTest(ShellTestCase):
    def test_captions_show_the_real_range_of_the_kit(self):
        kit = self.open(sections.MY_KIT)
        kit._on_sort("quantity_desc")
        self.assertEqual(kit.table.caption, "10-1")
        kit.sort_select.set("quantity")
        kit._on_sort("quantity")
        self.assertEqual(kit.table.caption, "1-10")
        self.assertEqual(kit.sort_select.shown_text(), "Сортировка: количество (1-10)")

    def test_range_follows_the_products(self):
        self.services.products  # демо: от 1 до 10
        pid = next(
            v.product.id
            for v in self.services.products.list_products(self.app.user.id)
            if v.product.name == "Парацетамол"
        )
        self.db.execute("UPDATE products SET quantity = 23 WHERE id = ?", (pid,))
        kit = self.open(sections.MY_KIT)
        kit._on_sort("quantity_desc")
        self.assertEqual(kit.table.caption, "23-1")
        self.assertIn("(23-1)", sorting.label_of("quantity_desc"))

    def test_other_captions_are_unchanged(self):
        self.assertEqual(sorting.caption_of("name"), "А-Я")


class AddedColumnTest(ShellTestCase):
    def test_kit_has_the_added_column_next_to_the_name(self):
        kit = self.open(sections.MY_KIT)
        header = kit.table._header_cells[2].findChildren(type(kit.summary))
        titles = [w.text() for w in header]
        self.assertIn("Дата добавления", titles)
        first = kit.table.row_texts[0]
        self.assertRegex(first[1], r"^\d\d\.\d\d\.\d{4}$")

    def test_header_click_sorts_by_the_date(self):
        kit = self.open(sections.MY_KIT)
        kit._on_header(sorting.kind_by_key("added"))
        self.assertEqual(kit.sort, "added")
        self.assertEqual(kit.table.caption_column, 1)


class ShoppingDialogSuggestionsTest(ShellTestCase):
    def test_word_forms_are_suggested_from_the_kit(self):
        dialog = AddItemDialog(self.app, self.services, self.app.user.id, lambda: None)
        self.settle()
        dialog.name.set("витамины")
        dialog.name._refresh_suggestions()
        self.assertIn(
            "Витамин D",
            [text.split(" · ")[0] for _v, text in dialog.name.popup.options],
        )
        dialog.close_modal()


class ListsScrollInsideTheCardTest(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        paging.AUTO_FIT = True
        self.addCleanup(setattr, paging, "AUTO_FIT", False)
        for number in range(40):
            self.services.shopping.add_manual(self.app.user.id, f"Товар {number}")
        self.app.resize(1160, 520)
        self.settle()

    def test_history_and_notifications_scroll_inside_but_the_page_does_not(self):
        for name in (sections.HISTORY, sections.NOTIFICATIONS):
            for number in range(30):
                self.db.execute(
                    "INSERT INTO history (user_id, action, description)"
                    " VALUES (?, 'product_added', ?)",
                    (self.app.user.id, f"Запись {number}"),
                )
            page = self.open(name)
            page.fit_rows()
            self.settle()
            self.assertEqual(self.shell._scroll.verticalScrollBar().maximum(), 0, name)
            self.assertTrue(hasattr(page, "_scroll"))

    def test_shopping_always_has_the_pager(self):
        page = self.open(sections.SHOPPING)
        self.assertTrue(page.summary.text().startswith("Показано"))
        self.assertTrue(hasattr(page, "pagination"))
