"""Тесты сортировки «Моя аптечка»: вид и подвид в одном списке, подписи в шапке."""

import unittest
from typing import List


from pharmacy.ui import sections, sorting
from pharmacy.ui.widgets.popup import PopupList
from tests.qt_helpers import ShellTestCase, click


class SortingDataTest(unittest.TestCase):
    def test_default_is_by_state(self):
        self.assertEqual(sorting.DEFAULT_SORT, "status")
        self.assertEqual(sorting.kind_of("status").key, "status")

    def test_every_kind_has_two_directions_that_fit_its_meaning(self):
        for kind in sorting.SORT_KINDS:
            self.assertEqual(len(kind.choices), 2, kind.key)
        names = {
            kind.key: [c.label for c in kind.choices] for kind in sorting.SORT_KINDS
        }
        self.assertEqual(names["name"], ["от А до Я", "от Я до А"])
        self.assertEqual(
            names["quantity"], ["от большего к меньшему", "от меньшего к большему"]
        )
        self.assertEqual(names["added"], ["сначала новые", "сначала старые"])
        self.assertEqual(names["status"], ["сначала просроченные", "сначала норма"])
        self.assertEqual(
            names["expiry"], ["сначала ближайшие", "сначала самые дальние"]
        )

    def test_values_are_unique_and_known_to_the_repository(self):
        from pharmacy.repositories.product_repository import SORT_ORDERS

        values = [c.value for k in sorting.SORT_KINDS for c in k.choices]
        self.assertEqual(len(values), len(set(values)))
        for value in values:
            if not value.startswith("status"):  # по состоянию считает сервис
                self.assertIn(value, SORT_ORDERS, value)

    def test_toggle_goes_to_the_other_direction_and_back(self):
        for kind in sorting.SORT_KINDS:
            first, second = (c.value for c in kind.choices)
            self.assertEqual(sorting.toggled(first), second)
            self.assertEqual(sorting.toggled(second), first)


class SortTestCase(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.open(sections.MY_KIT)

    @property
    def kit(self):
        return self.page

    def names(self) -> List[str]:
        return [row[0] for row in self.kit.table.row_texts]

    def column(self, index: int) -> List[str]:
        return [row[index] for row in self.kit.table.row_texts]

    def open_list(self) -> PopupList:
        select = self.kit.sort_select
        select.frame_pressed(None)
        self.settle()
        return select.popup

    def pick_in_list(self, popup: PopupList, value: object) -> None:
        """Нажимает на вариант списка так, как это делает мышь."""
        index = [v for v, _ in popup.options].index(value)
        y = 2 + 4 + index * 30 + 15
        click(popup, 12 + 20, y)
        self.settle()

    def choose(self, kind_key: str, value: str) -> None:
        popup = self.open_list()
        self.pick_in_list(popup, kind_key)
        self.pick_in_list(popup, value)


class EverySortTest(SortTestCase):
    def test_name_both_ways(self):
        self.choose("name", "name")
        names = self.names()
        self.assertEqual(names, sorted(names, key=str.casefold))
        self.choose("name", "name_desc")
        names = self.names()
        self.assertEqual(names, sorted(names, key=str.casefold, reverse=True))

    def test_quantity_both_ways(self):
        self.choose("quantity", "quantity_desc")
        amounts = [float(v) for v in self.column(3)]
        self.assertEqual(amounts, sorted(amounts, reverse=True))
        self.choose("quantity", "quantity")
        amounts = [float(v) for v in self.column(3)]
        self.assertEqual(amounts, sorted(amounts))

    def test_expiry_both_ways_with_empty_dates_last(self):
        def dates():
            return [d for d in self.column(5)]

        def key(text):
            return tuple(reversed(text.split(".")))

        self.choose("expiry", "expiry")
        values = dates()
        self.assertEqual(values[-1], "—")
        real = [key(d) for d in values if d != "—"]
        self.assertEqual(real, sorted(real))
        self.choose("expiry", "expiry_desc")
        values = dates()
        self.assertEqual(values[-1], "—")
        real = [key(d) for d in values if d != "—"]
        self.assertEqual(real, sorted(real, reverse=True))

    def test_category_both_ways(self):
        self.choose("category", "category")
        names = self.column(2)
        self.assertEqual(names, sorted(names, key=str.casefold))
        self.choose("category", "category_desc")
        names = self.column(2)
        self.assertEqual(names, sorted(names, key=str.casefold, reverse=True))

    def test_place_both_ways(self):
        self.choose("place", "place")
        places = [p for p in self.column(6) if p != "—"]
        self.assertEqual(places, sorted(places, key=str.casefold))
        self.choose("place", "place_desc")
        places = [p for p in self.column(6) if p != "—"]
        self.assertEqual(places, sorted(places, key=str.casefold, reverse=True))

    def test_added_both_ways(self):
        self.db.execute("UPDATE products SET created_at = '2026-01-01 10:00:00'")
        self.db.execute(
            "UPDATE products SET created_at = '2026-05-05 10:00:00' WHERE name = 'Бинт'"
        )
        self.open(sections.MY_KIT)
        self.choose("added", "added")
        self.assertEqual(self.names()[0], "Бинт")
        self.choose("added", "added_asc")
        self.assertEqual(self.names()[-1], "Бинт")

    def test_state_both_ways(self):
        self.choose("status", "status_ok")
        order = ["Норма", "Низкий остаток", "Скоро истекает", "Просрочен"]
        ranks = [order.index(s) for s in self.column(7)]
        self.assertEqual(ranks, sorted(ranks))
        self.choose("status", "status")
        self.assertEqual(self.column(7)[0], "Просрочен")


class HeaderClickTest(SortTestCase):
    def head(self, index):
        return self.kit.table._header_cells[index + 1]

    def test_click_on_the_sorted_column_flips_the_direction(self):
        self.choose("name", "name")
        click(self.head(0))
        self.settle()
        self.assertEqual(self.kit.sort, "name_desc")
        self.assertEqual(self.kit.table.caption, "Я-А")
        click(self.head(0))
        self.settle()
        self.assertEqual(self.kit.sort, "name")

    def test_click_on_another_column_sorts_by_it_from_the_first_direction(self):
        click(self.head(3))
        self.settle()
        self.assertEqual(self.kit.sort, "quantity_desc")
        self.assertEqual(self.kit.sort_select.get(), "quantity_desc")
        self.assertEqual(self.kit.table.caption_column, 3)

    def test_state_header_flips_between_the_two_orders(self):
        click(self.head(7))
        self.settle()
        self.assertEqual(self.kit.sort, "status_ok")
        self.assertEqual(self.column(7)[0], "Норма")

    def column(self, index):
        return [row[index] for row in self.kit.table.row_texts]


class PersistenceTest(SortTestCase):
    def test_choice_is_remembered_when_the_screen_is_rebuilt(self):
        self.choose("name", "name_desc")
        self.open(sections.HOME)
        self.open(sections.MY_KIT)
        self.assertEqual(self.kit.sort, "name_desc")
        self.assertEqual(self.kit.table.caption, "Я-А")

    def test_choice_is_saved_for_the_user(self):
        self.choose("quantity", "quantity")
        self.assertEqual(
            self.app.preferences.get(self.app.user.id, "kit_sort"), "quantity"
        )

    def test_unknown_saved_value_falls_back_to_the_state_sort(self):
        self.app.preferences.set(self.app.user.id, "kit_sort", "nonsense")
        self.open(sections.HOME)
        self.open(sections.MY_KIT)
        self.assertEqual(self.kit.sort, "status")


if __name__ == "__main__":
    unittest.main()
