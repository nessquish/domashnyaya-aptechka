"""Таблицы занимают окно до низа: число строк зависит от высоты окна."""

from pharmacy.ui import paging, sections
from tests.qt_helpers import ShellTestCase


class FitRowsTest(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        paging.AUTO_FIT = True
        self.addCleanup(setattr, paging, "AUTO_FIT", False)
        for number in range(40):
            self.services.shopping.add_manual(self.app.user.id, f"Товар {number}")

    def gap(self, page) -> int:
        """Сколько пустого места осталось между таблицей и низом окна."""
        card = page._card
        bottom = card.mapTo(page, card.rect().bottomLeft()).y()
        return self.shell.viewport_height() - bottom

    def open_fitted(self, name: str):
        page = self.open(name)
        page.fit_rows()
        self.settle()
        page.fit_rows()
        self.settle()
        return page

    def test_kit_table_reaches_the_bottom(self):
        page = self.open_fitted(sections.MY_KIT)
        rows = page.table.row_count
        total = len(self.services.products.list_products(self.app.user.id))
        if rows < total:  # не всё поместилось: под таблицей нет пустого места
            self.assertLess(self.gap(page), page.table.height() / rows + 60)

    def test_taller_window_shows_more_rows(self):
        page = self.open_fitted(sections.SHOPPING)
        before = page.table.row_count
        self.app.resize(self.app.width(), self.app.height() + 300)
        self.settle()
        page.fit_rows()
        self.settle()
        self.assertGreater(page.table.row_count, before)

    def test_shopping_is_paged(self):
        page = self.open_fitted(sections.SHOPPING)
        self.assertLess(page.table.row_count, 44)
        self.assertEqual(page.pagination is not None, True)
