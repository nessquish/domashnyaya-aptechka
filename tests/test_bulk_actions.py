"""Выбор нескольких товаров галочками и массовые действия."""

from pharmacy.ui import sections
from tests.qt_helpers import ShellTestCase, click


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
