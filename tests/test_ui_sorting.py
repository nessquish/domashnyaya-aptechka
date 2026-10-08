"""Тесты сортировки «Моя аптечка»: вид и подвид в одном списке, подписи в шапке."""

import unittest
from typing import List

from PySide6.QtWidgets import QLabel, QWidget

from pharmacy.ui import sections, sorting, theme
from pharmacy.ui.widgets.popup import PopupList
from pharmacy.ui.widgets.sortselect import BACK, SortSelect
from tests.qt_helpers import ShellTestCase, click, find_all
from tests.test_ui_add_product import BUTTON, AddProductTestCase


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

    def test_captions_for_the_header(self):
        self.assertEqual(sorting.choice_of("name").caption, "А-Я")
        self.assertEqual(sorting.choice_of("name_desc").caption, "Я-А")
        self.assertEqual(sorting.choice_of("quantity_desc").caption, "9-0")
        self.assertEqual(sorting.choice_of("quantity").caption, "0-9")

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

    def test_columns_map_to_kinds(self):
        self.assertEqual(sorting.kind_for_column(0).key, "name")
        self.assertEqual(sorting.kind_for_column(2).key, "quantity")
        self.assertEqual(sorting.kind_for_column(6).key, "status")
        self.assertIsNone(sorting.kind_for_column(3))  # «Ед. изм.» не сортируется
        self.assertIsNone(sorting.kind_by_key("added").column)

    def test_field_text(self):
        self.assertEqual(sorting.field_text("name"), "название (А-Я)")
        self.assertEqual(sorting.field_text("status_ok"), "состояние (норма)")

    def test_unknown_value(self):
        self.assertFalse(sorting.is_sort("whatever"))
        self.assertFalse(sorting.is_sort(None))


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


class DefaultSortTest(SortTestCase):
    def test_without_a_choice_the_table_is_sorted_by_state(self):
        self.assertEqual(self.kit.sort, "status")
        self.assertEqual(self.names()[0], "Активированный уголь")
        order = ["Просрочен", "Скоро истекает", "Низкий остаток", "Норма"]
        ranks = [order.index(s) for s in self.column(6)]
        self.assertEqual(ranks, sorted(ranks))

    def test_the_field_shows_the_current_sort(self):
        self.assertEqual(
            self.kit.sort_select.shown_text(), "Сортировка: состояние (просроч.)"
        )

    def test_caption_is_next_to_the_state_column_only(self):
        table = self.kit.table
        self.assertEqual(table.caption_column, 6)
        self.assertEqual(table.caption, "просроч.")

    def test_expiry_header_has_no_arrow_or_caption_any_more(self):
        texts = [w.text() for w in self.kit.table._header_cells[5].findChildren(QLabel)]
        self.assertEqual(texts, ["Срок годности"])


class TwoStepListTest(SortTestCase):
    def test_first_the_kinds_are_shown(self):
        popup = self.open_list()
        labels = [label for _value, label in popup.options]
        self.assertEqual(
            labels,
            [
                "По состоянию",
                "По названию",
                "По количеству",
                "По сроку годности",
                "По категории",
                "По месту хранения",
                "По дате добавления",
            ],
        )

    def test_picking_a_kind_changes_the_same_list_to_its_directions(self):
        popup = self.open_list()
        self.pick_in_list(popup, "name")
        self.assertIs(self.kit.sort_select.popup, popup)  # тот же список, не новый
        self.assertTrue(popup.isVisible())
        labels = [label for _value, label in popup.options]
        self.assertEqual(labels[1:], ["от А до Я", "от Я до А"])
        self.assertIn("Назад", labels[0])

    def test_quantity_directions(self):
        popup = self.open_list()
        self.pick_in_list(popup, "quantity")
        labels = [label for _value, label in popup.options][1:]
        self.assertEqual(labels, ["от большего к меньшему", "от меньшего к большему"])

    def test_no_extra_window_is_created(self):
        before = {id(w) for w in self.app.findChildren(QWidget) if w.isWindow()}
        popup = self.open_list()
        self.pick_in_list(popup, "name")
        after = {id(w) for w in self.app.findChildren(QWidget) if w.isWindow()}
        self.assertEqual(before, after)
        self.assertFalse(popup.isWindow())
        self.assertIs(popup.parentWidget(), self.app)

    def test_picking_a_direction_applies_it_and_closes_the_list(self):
        popup = self.open_list()
        self.pick_in_list(popup, "name")
        self.pick_in_list(popup, "name_desc")
        self.assertIsNone(self.kit.sort_select.popup)
        self.assertEqual(self.kit.sort, "name_desc")
        names = self.names()
        self.assertEqual(names, sorted(names, key=str.casefold, reverse=True))

    def test_back_returns_to_the_kinds(self):
        popup = self.open_list()
        self.pick_in_list(popup, "quantity")
        self.pick_in_list(popup, BACK)
        self.assertTrue(popup.isVisible())
        self.assertEqual(popup.options[0][1], "По состоянию")
        self.assertEqual(len(popup.options), 7)

    def test_current_direction_is_highlighted_inside_its_kind(self):
        popup = self.open_list()
        self.pick_in_list(popup, "status")
        self.assertEqual(popup._selected, "status")
        self.pick_in_list(popup, BACK)
        self.assertEqual(popup._selected, "status")  # вид выделен
        popup.close_list()

    def test_list_closes_on_escape_and_outside_click_without_changes(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        popup = self.open_list()
        self.pick_in_list(popup, "name")
        QTest.keyClick(popup, Qt.Key.Key_Escape)
        self.settle()
        self.assertIsNone(self.kit.sort_select.popup)
        self.assertEqual(self.kit.sort, "status")

    def test_clicking_the_field_again_closes_the_list(self):
        self.open_list()
        click(self.kit.sort_select.frame, 40, 16)
        self.settle()
        self.assertIsNone(self.kit.sort_select.popup)

    def test_list_opens_again_from_the_kinds_every_time(self):
        popup = self.open_list()
        self.pick_in_list(popup, "name")
        popup.close_list()
        self.settle()
        popup = self.open_list()
        self.assertEqual(len(popup.options), 7)

    def test_select_is_the_two_step_widget(self):
        self.assertIsInstance(self.kit.sort_select, SortSelect)


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
        amounts = [float(v) for v in self.column(2)]
        self.assertEqual(amounts, sorted(amounts, reverse=True))
        self.choose("quantity", "quantity")
        amounts = [float(v) for v in self.column(2)]
        self.assertEqual(amounts, sorted(amounts))

    def test_expiry_both_ways_with_empty_dates_last(self):
        def dates():
            return [d for d in self.column(4)]

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
        names = self.column(1)
        self.assertEqual(names, sorted(names, key=str.casefold))
        self.choose("category", "category_desc")
        names = self.column(1)
        self.assertEqual(names, sorted(names, key=str.casefold, reverse=True))

    def test_place_both_ways(self):
        self.choose("place", "place")
        places = [p for p in self.column(5) if p != "—"]
        self.assertEqual(places, sorted(places, key=str.casefold))
        self.choose("place", "place_desc")
        places = [p for p in self.column(5) if p != "—"]
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
        ranks = [order.index(s) for s in self.column(6)]
        self.assertEqual(ranks, sorted(ranks))
        self.choose("status", "status")
        self.assertEqual(self.column(6)[0], "Просрочен")

    def test_field_text_follows_the_choice(self):
        self.choose("quantity", "quantity_desc")
        self.assertEqual(
            self.kit.sort_select.shown_text(), "Сортировка: количество (9-0)"
        )

    def test_page_resets_to_the_first(self):
        from pharmacy.db.seed import seed_bulk

        seed_bulk(self.db, self.app.user.id, count=20)
        self.open(sections.MY_KIT)
        self.kit._on_page(3)
        self.choose("name", "name")
        self.assertEqual(self.kit._page, 1)


class HeaderCaptionTest(SortTestCase):
    def caption_columns(self):
        return [
            index - 1  # первый столбец с флажками не считается
            for index, cell in enumerate(self.kit.table._header_cells)
            if len(cell.findChildren(QLabel)) > 1
        ]

    def test_caption_for_each_kind_next_to_its_column(self):
        cases = {
            ("name", "name"): (0, "А-Я"),
            ("name", "name_desc"): (0, "Я-А"),
            ("quantity", "quantity_desc"): (2, "9-0"),
            ("quantity", "quantity"): (2, "0-9"),
            ("expiry", "expiry"): (4, "ближе"),
            ("expiry", "expiry_desc"): (4, "дальше"),
            ("category", "category"): (1, "А-Я"),
            ("place", "place_desc"): (5, "Я-А"),
            ("status", "status_ok"): (6, "норма"),
        }
        for (kind, value), (column, caption) in cases.items():
            self.choose(kind, value)
            self.assertEqual(self.kit.table.caption_column, column, value)
            self.assertEqual(self.kit.table.caption, caption, value)
            self.assertEqual(self.caption_columns(), [column], value)

    def test_caption_is_purple_text_in_the_header(self):
        self.choose("name", "name")
        label = self.kit.table._header_cells[1].findChildren(QLabel)[-1]
        self.assertEqual(label.text(), "А-Я")
        self.assertEqual(
            label.palette().windowText().color().name().upper(),
            theme.LIGHT.primary.upper(),
        )

    def test_added_sort_has_no_column_so_no_caption(self):
        self.choose("added", "added")
        self.assertIsNone(self.kit.table.caption_column)
        self.assertEqual(self.caption_columns(), [])

    def test_caption_moves_when_the_sort_changes(self):
        self.choose("name", "name")
        self.assertEqual(self.caption_columns(), [0])
        self.choose("quantity", "quantity")
        self.assertEqual(self.caption_columns(), [2])


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
        click(self.head(2))
        self.settle()
        self.assertEqual(self.kit.sort, "quantity_desc")
        self.assertEqual(self.kit.sort_select.get(), "quantity_desc")
        self.assertEqual(self.kit.table.caption_column, 2)

    def test_state_header_flips_between_the_two_orders(self):
        click(self.head(6))
        self.settle()
        self.assertEqual(self.kit.sort, "status_ok")
        self.assertEqual(self.column(6)[0], "Норма")

    def column(self, index):
        return [row[index] for row in self.kit.table.row_texts]

    def test_unit_column_is_not_sortable(self):
        self.assertNotEqual(
            self.head(3).cursor().shape(), self.head(2).cursor().shape()
        )
        click(self.head(3))
        self.settle()
        self.assertEqual(self.kit.sort, "status")

    def test_tips_describe_the_next_step(self):
        self.choose("name", "name")
        self.assertIn("от А до Я", self.head(0).toolTip())
        self.assertIn("от Я до А", self.head(0).toolTip())
        self.assertIn("количеству", self.head(2).toolTip())


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

    def test_other_users_do_not_share_the_choice(self):
        self.choose("name", "name")
        self.assertEqual(self.app.preferences.get(999, "kit_sort", "status"), "status")


class AddProductSortTest(AddProductTestCase):
    """Новый товар сразу встаёт в таблицу по выбранной сортировке."""

    def add(self, **values):
        self.buttons(BUTTON)[0].invoke()
        self.settle()
        dialog = find_all(self.app, type(self.dialogs()[0]))[0]
        self.fill(dialog, **values)
        dialog.save_button.invoke()
        self.settle()

    def kit(self):
        return self.page

    def test_without_a_chosen_sort_the_new_product_goes_by_state(self):
        self.add(name="Просроченный новый", expiry_date="01.01.2000")
        self.assertEqual(
            self.names()[0], "Просроченный новый"
        )  # самая старая просрочка

    def test_good_new_product_goes_to_the_normal_group(self):
        self.add(name="Свежий", expiry_date="01.01.2035")
        # Норма с самым поздним сроком: в конце списка, таблица открыта на его странице.
        self.assertIn("Свежий", self.names())
        self.assertEqual(self.names()[-1], "Свежий")

    def test_current_name_sort_is_respected(self):
        self.open(sections.MY_KIT)
        self.page.sort_select.set("name")
        self.page._on_sort("name")
        self.add(name="Аааа первый", expiry_date="01.01.2035")
        self.assertEqual(self.page.sort, "name")
        self.assertEqual(self.names()[0], "Аааа первый")

    def test_current_quantity_sort_is_respected(self):
        self.open(sections.MY_KIT)
        self.page._on_sort("quantity_desc")
        self.add(name="Целый ящик", quantity="9999", expiry_date="01.01.2035")
        self.assertEqual(self.names()[0], "Целый ящик")

    def test_table_opens_on_the_page_with_the_new_product(self):
        self.open(sections.MY_KIT)
        self.page._on_sort("name_desc")
        self.add(name="Аааа последний", expiry_date="01.01.2035")  # в конце по Я-А
        self.assertEqual(self.page._page, 2)
        self.assertIn("Аааа последний", self.names())

    def test_sort_from_the_dashboard_flow_uses_the_saved_choice(self):
        self.app.preferences.set(self.app.user.id, "kit_sort", "name_desc")
        self.add(name="Ярлык", expiry_date="01.01.2035")
        self.assertEqual(self.page.sort, "name_desc")
        self.assertEqual(self.names()[0], "Ярлык")


if __name__ == "__main__":
    unittest.main()
