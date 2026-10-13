"""Порог низкого остатка, дата добавления, прокрутка списков и массовые действия."""

from pharmacy.services.notification_service import NotifyOptions
from pharmacy.services.status import ProductStatus
from pharmacy.ui import paging, sections, sorting
from pharmacy.ui.screens.shopping import AddItemDialog
from pharmacy.utils.textmatch import name_matches
from tests.qt_helpers import ShellTestCase, click


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


class ListShrinksWithItsContentTest(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        paging.AUTO_FIT = True
        self.addCleanup(setattr, paging, "AUTO_FIT", False)
        self.app.resize(1160, 900)
        self.settle()

    def pause(self):
        import time

        time.sleep(0.12)
        self.settle()
        self.settle()

    def test_notifications_get_smaller_when_there_are_fewer(self):
        page = self.open(sections.NOTIFICATIONS)
        self.pause()
        full = page._scroll.height()
        page._on_tab(3)  # только «Срок годности»: уведомлений меньше
        self.pause()
        self.assertLess(page._scroll.height(), full)
        self.assertEqual(
            page._scroll.height(), page._scroll.widget().sizeHint().height()
        )

    def test_history_gets_smaller_with_a_search(self):
        page = self.open(sections.HISTORY)
        self.pause()
        full = page._scroll.height()
        page._query = "ибупрофен"
        page._reload()
        self.pause()
        self.assertLess(page._scroll.height(), full)

    def test_one_item_makes_a_small_table(self):
        page = self.open(sections.NOTIFICATIONS)
        for number in range(1, 9):
            self.services.notifications.delete(self.app.user.id, number)
        page._reload()
        self.pause()
        self.assertLess(page._card.height(), 200)


class KitSelectionTest(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.kit = self.open(sections.MY_KIT)

    def boxes(self):
        return self.kit.table.check_widgets()

    def pick(self, index):
        click(self.boxes()[index])
        self.settle()

    def test_checkbox_selects_and_shows_bar(self):
        self.assertFalse(self.kit.bar.isVisible())
        self.pick(0)
        self.pick(1)
        self.assertEqual(len(self.kit.selected), 2)
        self.assertTrue(self.kit.bar.isVisible())
        self.assertEqual(self.kit.bar.text, "Выбрано: 2")

    def test_row_click_toggles_selection(self):
        row = self.kit.table._cells[0][2]
        click(row)
        self.settle()
        self.assertEqual(len(self.kit.selected), 1)
        self.assertTrue(self.boxes()[0].value)
        click(row)
        self.settle()
        self.assertEqual(self.kit.selected, set())

    def test_header_checkbox_selects_the_page(self):
        self.kit._toggle_page(True)
        self.assertEqual(len(self.kit.selected), self.kit.table.row_count)
        self.assertTrue(self.kit.select_page.value)

    def test_select_everything_and_clear(self):
        self.kit._select_everything()
        total = len(self.services.products.list_products(self.app.user.id))
        self.assertEqual(len(self.kit.selected), total)
        self.kit._clear_selection()
        self.assertEqual(self.kit.selected, set())
        self.assertFalse(self.kit.bar.isVisible())

    def test_add_selected_to_shopping(self):
        self.pick(0)
        self.pick(1)
        before = len(self.services.shopping.list_items(self.app.user.id))
        self.kit._add_to_shopping()
        after = len(self.services.shopping.list_items(self.app.user.id))
        self.assertGreater(after, before)
        self.assertEqual(self.kit.selected, set())

    def test_delete_selected(self):
        total = len(self.services.products.list_products(self.app.user.id))
        self.pick(0)
        self.pick(1)
        self.kit._delete_selected()
        left = len(self.services.products.list_products(self.app.user.id))
        self.assertEqual(left, total - 2)
        self.assertEqual(self.kit.selected, set())

    def test_change_category_of_selected(self):
        categories = self.services.products.list_categories()
        self.pick(0)
        target = categories[-1].id
        self.kit._change_category(target)
        name = self.kit.table.row_texts[0][0]
        product = next(
            v.product
            for v in self.services.products.list_products(self.app.user.id)
            if v.product.name == name
        )
        self.assertEqual(product.category_id, target)


class ShoppingSelectionTest(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.open(sections.SHOPPING)

    def test_row_click_toggles_selection(self):
        click(self.page.table._cells[0][1])
        self.settle()
        self.assertEqual(len(self.page.selected), 1)

    def test_toggle_keeps_the_rows(self):
        rows = self.page.table._rows[:]
        click(self.page.table.cell_widgets(0)[0])
        self.settle()
        self.assertTrue(set(rows) <= set(self.page.table._rows) | set(rows))
        self.assertEqual(len(self.page.selected), 1)

    def test_select_everything_and_clear(self):
        self.page._select_everything()
        self.assertEqual(len(self.page.selected), 4)
        self.page._clear_selection()
        self.assertEqual(self.page.selected, set())

    def test_bought_items_can_be_returned(self):
        self.page._on_tab(2)
        self.page._select_everything()
        self.assertEqual(self.page.bought_button.text(), "Вернуть в список")
        self.page._mark_bought()
        open_items = self.services.shopping.list_items(self.app.user.id, False)
        self.assertEqual(len(open_items), 4)


class ClearHistoryTest(ShellTestCase):
    def test_clear_removes_only_own_history(self):
        page = self.open(sections.HISTORY)
        self.assertTrue(self.services.history.list_history(self.app.user.id))
        self.assertTrue(page.clear_button.isEnabled())
        page._clear()
        self.assertEqual(self.services.history.list_history(self.app.user.id), [])
        self.assertEqual(page.event_rows, [])
        self.assertFalse(page.clear_button.isEnabled())

    def test_button_asks_for_confirmation(self):
        page = self.open(sections.HISTORY)
        page.clear_button.invoke()
        self.settle()
        self.assertTrue(self.buttons("Очистить"))
        self.assertTrue(self.services.history.list_history(self.app.user.id))


class NarrowWindowTest(ShellTestCase):
    def test_sidebar_is_never_hidden_automatically(self):
        self.app.resize(900, 640)
        self.settle()
        self.assertTrue(self.shell.sidebar.isVisible())
        self.assertFalse(self.shell.sidebar_collapsed)

    def test_user_can_still_collapse_it(self):
        self.app.resize(900, 640)
        self.shell.set_sidebar_collapsed(True)
        self.settle()
        self.assertFalse(self.shell.sidebar.isVisible())
        self.assertTrue(self.shell._rail.isVisible())
        self.app.resize(1300, 640)
        self.settle()
        self.assertFalse(self.shell.sidebar.isVisible())

    def test_window_can_be_narrower_than_the_content(self):
        self.assertLessEqual(self.app.minimumWidth(), 800)


class ProfileLinkTest(ShellTestCase):
    def test_click_on_the_user_opens_the_account(self):
        click(self.shell.sidebar.profile)
        self.settle()
        self.assertEqual(self.shell.section, sections.SETTINGS)
        self.assertEqual(self.page.section, "account")

    def test_click_on_the_name_works_too(self):
        from PySide6.QtWidgets import QLabel

        name = next(
            w
            for w in self.shell.sidebar.profile.findChildren(QLabel)
            if w.text() == "Анастасия"
        )
        click(name)
        self.settle()
        self.assertEqual(self.page.section, "account")
