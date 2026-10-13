"""Тесты выпадающего списка, переключателей, таблицы и расширенных полей."""

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.common import label
from pharmacy.ui.widgets.controls import Segmented
from pharmacy.ui.widgets.popup import SHADOW_PAD, PopupList
from pharmacy.ui.widgets.select import Select
from pharmacy.ui.widgets.table import Column, DataTable, TextCell
from tests.qt_helpers import WidgetTestCase, click


class Holder(WidgetTestCase):
    """Окно с вертикальной раскладкой: виджеты прижаты к верху."""

    def setUp(self) -> None:
        super().setUp()
        self.layout = QVBoxLayout(self.root)
        self.layout.setContentsMargins(0, 0, 0, 0)

    def add(self, widget: QWidget, alignment=Qt.AlignmentFlag(0)) -> QWidget:
        self.layout.addWidget(widget, 0, alignment | Qt.AlignmentFlag.AlignTop)
        self.settle()
        return widget


def open_list(select: Select) -> PopupList:
    click(select.frame, 40, 16)
    select.window()  # окно уже знает о новом виджете
    return select.popup


class SelectTest(Holder):
    OPTIONS = [(1, "Лекарства"), (2, "Бытовая химия"), (3, "Гигиена")]

    def make(self, **kwargs) -> Select:
        return self.add(Select(self.OPTIONS, label_text="Категория", **kwargs))

    def test_value_is_not_the_label(self):
        select = self.make(value=2)
        self.assertEqual(select.get(), 2)

    def test_set_changes_value(self):
        select = self.make()
        select.set(3)
        self.assertEqual(select.value, 3)

    def test_click_opens_the_list_and_pick_changes_value(self):
        picked: List[object] = []
        select = self.make(on_change=picked.append)
        popup = open_list(select)
        self.assertIsInstance(popup, PopupList)
        self.assertTrue(popup.isVisible())
        popup._on_pick(2)
        popup.close_list()
        self.settle()
        self.assertEqual(select.get(), 2)
        self.assertEqual(picked, [2])
        self.assertIsNone(select.popup)

    def test_click_on_a_row_of_the_list_picks_it(self):
        picked: List[object] = []
        select = self.make(on_change=picked.append)
        popup = open_list(select)
        row = 1  # вторая строка списка
        y = 2 + 4 + row * 30 + 15
        click(popup, SHADOW_PAD + 20, y)
        self.settle()
        self.assertEqual(picked, [2])
        self.assertIsNone(select.popup)

    def test_click_elsewhere_closes_the_list_and_keeps_the_value(self):
        select = self.make(value=1)
        other = self.add(Button("другая кнопка"), Qt.AlignmentFlag.AlignLeft)
        open_list(select)
        self.assertIsNotNone(select.popup)
        click(other)
        self.settle()
        self.assertIsNone(select.popup)
        self.assertEqual(select.get(), 1)

    def test_clicking_the_same_select_twice_closes_the_list(self):
        select = self.make()
        open_list(select)
        click(select.frame, 40, 16)
        self.settle()
        self.assertIsNone(select.popup)

    def test_popup_closes_on_escape(self):
        select = self.make()
        popup = open_list(select)
        QTest.keyClick(popup, Qt.Key.Key_Escape)
        self.settle()
        self.assertIsNone(select.popup)

    def test_error_is_cleared_after_pick(self):
        select = self.make()
        select.set_error("Выберите категорию")
        select._pick(1)
        self.assertIsNone(select.error)


class _Wheel:
    """Колесо мыши для вызова обработчика напрямую."""

    def __init__(self, delta: int) -> None:
        self._delta = delta

    def angleDelta(self):
        class Point:
            def __init__(self, y):
                self._y = y

            def y(self):
                return self._y

        return Point(self._delta)


class SegmentedTest(Holder):
    def make(self, variant="tabs") -> Segmented:
        changes: List[int] = []
        seg = self.add(
            Segmented(
                ["Все · 4", "Не куплено · 3", "Куплено · 1"],
                0,
                changes.append,
                variant,
            ),
            Qt.AlignmentFlag.AlignLeft,
        )
        seg.changes = changes
        return seg

    def test_click_selects_item(self):
        for variant in ("tabs", "outline"):
            seg = self.make(variant)
            left, right = seg.spans[1]
            click(seg, (left + right) // 2, 15)
            self.assertEqual(seg.active, 1)
            self.assertEqual(seg.changes, [1])

    def test_clicking_active_item_does_nothing(self):
        seg = self.make()
        left, right = seg.spans[0]
        click(seg, (left + right) // 2, 15)
        self.assertEqual(seg.changes, [])

    def test_select_is_silent(self):
        seg = self.make()
        seg.select(2)
        self.assertEqual(seg.active, 2)
        self.assertEqual(seg.changes, [])

    def test_set_items_updates_labels(self):
        seg = self.make()
        before = seg.width()
        seg.set_items(["Все · 1000", "Не куплено · 3", "Куплено · 1"])
        self.assertGreater(seg.width(), before)

    def test_unknown_variant(self):
        with self.assertRaises(ValueError):
            Segmented(["a"], variant="x")


class DataTableTest(Holder):
    def make(self) -> DataTable:
        table = DataTable(
            [
                Column("Название", 3),
                Column("Срок", 2),
                Column("", fixed=40),
            ],
        )
        return self.add(table)

    def test_rows_are_added_and_cleared(self):
        table = self.make()
        table.add_row(["Бинт", "01.01.2027", "x"])
        table.add_row(["Вата", "02.01.2027", "y"])
        self.settle()
        self.assertEqual(table.row_count, 2)
        self.assertEqual(table.row_texts[0], ["Бинт", "01.01.2027", "x"])
        table.clear()
        self.settle()
        self.assertEqual(table.row_count, 0)
        self.assertEqual(table.row_texts, [])

    def test_link_cell_calls_command(self):
        calls: List[int] = []
        table = self.make()
        table.add_row(
            [
                TextCell("Бинт", "primary", True, on_click=lambda: calls.append(1)),
                "-",
                "-",
            ]
        )
        self.settle()
        click(table.cell_widgets(0)[0])
        self.assertEqual(calls, [1])

    def test_widget_cells(self):
        table = self.make()
        table.add_row(["Бинт", lambda: label("виджет"), ""])
        self.settle()
        self.assertEqual(table.cell_widgets(1)[0].text(), "виджет")

    def test_selected_row_has_highlight(self):
        table = self.make()
        table.add_row(["a", "b", "c"])
        plain = len(table._rows)
        table.add_row(["a", "b", "c"], selected=True)
        # У выбранной строки добавляется ещё и подложка.
        self.assertEqual(len(table._rows) - plain, plain + 1)

    def test_sort_caption_is_shown_only_next_to_one_column(self):
        table = self.make()
        table.set_sort_caption(1, "А-Я")
        self.assertEqual(table.caption_column, 1)
        self.assertEqual(table.caption, "А-Я")
        texts = [w.text() for w in table._header_cells[1].findChildren(QLabel)]
        self.assertEqual(texts, ["Срок", "А-Я"])
        for other in (0, 2):
            texts = [w.text() for w in table._header_cells[other].findChildren(QLabel)]
            self.assertNotIn("А-Я", texts)
        table.set_sort_caption(None)
        self.assertIsNone(table.caption_column)

    def test_header_click_and_tip(self):
        calls: List[int] = []
        table = self.make()
        table.set_header_click(0, lambda: calls.append(1), "Подсказка")
        click(table._header_cells[0])
        self.assertEqual(calls, [1])
        self.assertEqual(table._header_cells[0].toolTip(), "Подсказка")
        table.set_header_tip(0, "Другая")
        self.assertEqual(table._header_cells[0].toolTip(), "Другая")
