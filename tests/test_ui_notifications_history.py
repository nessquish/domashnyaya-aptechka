"""Тесты экранов «Уведомления» и «История», периодов и прокрутки."""

import unittest
from datetime import date, datetime, timedelta
from typing import List

from PySide6.QtWidgets import QLabel, QWidget

from pharmacy.models import HistoryAction, NotificationKind
from pharmacy.ui import periods, sections
from pharmacy.ui.screens.history import HistoryScreen, day_title, group_by_day
from pharmacy.ui.screens.notifications import NotificationsScreen, _when
from pharmacy.ui.screens.product_card import ProductCardDialog
from pharmacy.ui.theme import SHADOW_PAD
from pharmacy.ui.widgets.badge import Badge
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.scroll import ScrollArea
from tests.qt_helpers import ShellTestCase, WidgetTestCase, click, find_all


class PeriodsTest(unittest.TestCase):
    TODAY = date(2026, 10, 5)

    def test_all_time_has_no_start(self):
        self.assertIsNone(periods.since(periods.ALL_TIME, self.TODAY))

    def test_today_week_month(self):
        self.assertEqual(periods.since(periods.TODAY, self.TODAY), self.TODAY)
        self.assertEqual(periods.since(periods.WEEK, self.TODAY), date(2026, 9, 29))
        self.assertEqual(periods.since(periods.MONTH, self.TODAY), date(2026, 9, 6))

    def test_unknown_period(self):
        with self.assertRaises(KeyError):
            periods.since("year", self.TODAY)

    def test_every_period_has_a_label(self):
        keys = {key for key, _ in periods.PERIODS}
        self.assertEqual(keys, {"all", "today", "week", "month"})


class HelpersTest(unittest.TestCase):
    def test_when_today_and_other_day(self):
        today = date(2026, 10, 5)
        self.assertEqual(_when("2026-10-05 09:00:12", today), "сегодня, 09:00")
        self.assertEqual(_when("2026-09-30 18:30:00", today), "30.09.2026")

    def test_day_title(self):
        today = date(2026, 10, 1)
        self.assertEqual(day_title(today, today), "Сегодня, 01.10.2026")
        self.assertEqual(day_title(date(2026, 9, 30), today), "30.09.2026")

    def test_group_by_day_keeps_order(self):
        class Record:
            def __init__(self, stamp):
                self.created_at = stamp

        records = [
            Record("2026-10-03 10:00:00"),
            Record("2026-10-03 09:00:00"),
            Record("2026-10-01 12:00:00"),
        ]
        groups = group_by_day(records)
        self.assertEqual(list(groups), [date(2026, 10, 3), date(2026, 10, 1)])
        self.assertEqual(len(groups[date(2026, 10, 3)]), 2)


class NotificationsTest(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.open(sections.NOTIFICATIONS)

    @property
    def notifications_page(self) -> NotificationsScreen:
        return self.page

    def notifications(self):
        return self.services.notifications.list_notifications(self.app.user.id)

    def titles(self) -> List[str]:
        names = {
            "Срок годности истёк",
            "Скоро истекает срок годности",
            "Низкий остаток",
        }
        return [
            w.text() for w in find_all(self.page._card, QLabel) if w.text() in names
        ]

    def test_lists_all_notifications(self):
        self.assertEqual(len(self.titles()), len(self.notifications()))
        self.assertEqual(len(self.page.rows), len(self.notifications()))

    def test_tab_labels_have_counts(self):
        total = len(self.notifications())
        labels = self.page._tab_labels()
        self.assertEqual(labels[0], f"Все · {total}")
        self.assertEqual(labels[1], f"Непрочитанные · {total}")

    def test_expiry_tab_shows_only_expiry_kinds(self):
        self.page._on_tab(2)
        kinds = {n.kind for n in self.page._visible()}
        self.assertTrue(kinds <= {NotificationKind.EXPIRED, NotificationKind.EXPIRING})
        self.assertTrue(kinds)

    def test_low_stock_tab(self):
        self.page._on_tab(3)
        kinds = {n.kind for n in self.page._visible()}
        self.assertEqual(kinds, {NotificationKind.LOW_STOCK})

    def test_read_all_updates_everything(self):
        self.buttons("Прочитать все")[0].invoke()
        self.settle()
        self.assertEqual(self.services.notifications.count_unread(self.app.user.id), 0)
        self.assertTrue(self.page._tab_labels()[1].endswith("· 0"))
        self.page._on_tab(1)
        self.settle()
        self.assertEqual(self.titles(), [])
        self.assertIn(
            "Уведомлений нет", [w.text() for w in find_all(self.page, QLabel)]
        )

    def test_clear_asks_first_then_removes_everything(self):
        self.page.clear_button.invoke()
        self.settle()
        self.assertTrue(self.notifications())
        self.buttons("Очистить")[0].invoke()
        self.settle()
        self.assertEqual(self.notifications(), [])
        self.assertFalse(self.page.clear_button.enabled)
        self.assertIn(
            "Уведомлений нет", [w.text() for w in find_all(self.page, QLabel)]
        )

    def test_unread_tab_hides_read_items(self):
        first = self.notifications()[0]
        self.services.notifications.mark_read(self.app.user.id, first.id)
        self.page._on_tab(1)
        self.assertNotIn(first.id, [n.id for n in self.page._visible()])

    def test_period_filter(self):
        first = self.notifications()[0]
        self.db.execute(
            "UPDATE notifications SET created_at = '2020-01-01 10:00:00' WHERE id = ?",
            (first.id,),
        )
        self.page._on_period(periods.WEEK)
        self.assertNotIn(first.id, [n.id for n in self.page._visible()])
        self.page._on_period(periods.ALL_TIME)
        self.assertIn(first.id, [n.id for n in self.page._visible()])

    def test_period_select_changes_the_list(self):
        self.page.period_select._pick(periods.TODAY)
        self.assertEqual(self.page._period, periods.TODAY)

    def test_delete_removes_one_notification(self):
        before = len(self.notifications())
        self.page._delete(self.notifications()[0].id)
        self.assertEqual(len(self.notifications()), before - 1)

    def test_close_cross_deletes_the_notification(self):
        before = len(self.notifications())
        row = self.page.rows[0]
        cross = [
            w
            for w in row.findChildren(QLabel)
            if w.pixmap() is not None and not w.pixmap().isNull()
        ][-1]
        click(cross)
        self.settle()
        self.assertEqual(len(self.notifications()), before - 1)

    def test_delete_of_missing_notification_is_ignored(self):
        self.page._delete(99999)

    def test_open_product_marks_read_and_opens_card(self):
        target = self.notifications()[0]
        self.buttons("Открыть товар")[0].invoke()
        self.settle()
        self.assertEqual(len(find_all(self.app, ProductCardDialog)), 1)
        self.assertIsInstance(self.page, NotificationsScreen)
        refreshed = self.services.notifications.list_notifications(self.app.user.id)
        self.assertTrue(next(n for n in refreshed if n.id == target.id).is_read)

    def test_add_to_list_replaces_button_with_badge(self):
        add = self.buttons("В список покупок")
        self.assertTrue(add)
        before = len(self.services.shopping.list_items(self.app.user.id, False))
        add[0].invoke()
        self.settle()
        after = len(self.services.shopping.list_items(self.app.user.id, False))
        self.assertEqual(after, before + 1)
        self.assertEqual(len(self.buttons("В список покупок")), len(add) - 1)

    def test_action_columns_are_aligned_in_every_row(self):
        # В демо-данных есть и строки с кнопкой, и строки с плашкой «В списке».
        opens = [b for b in find_all(self.page, Button) if b.text() == "Открыть товар"]
        self.assertGreater(len(opens), 2)
        lefts = {b.mapTo(self.page, b.rect().topLeft()).x() for b in opens}
        self.assertEqual(len(lefts), 1)
        self.assertEqual({b.width() for b in opens}, {opens[0].width()})
        buttons = [
            b for b in find_all(self.page, Button) if b.text() == "В список покупок"
        ]
        badges = [w for w in find_all(self.page, Badge) if w.text == "В списке покупок"]
        self.assertTrue(buttons and badges)
        # Видимый левый край кнопки смещён внутрь на поле под тень.
        edges = {
            b.mapTo(self.page, b.rect().topLeft()).x() + SHADOW_PAD for b in buttons
        }
        edges |= {w.mapTo(self.page, w.rect().topLeft()).x() for w in badges}
        self.assertEqual(len(edges), 1)

    def test_sidebar_counter_follows_reading(self):
        self.buttons("Прочитать все")[0].invoke()
        self.settle()
        self.assertEqual(self.shell.sidebar.item(sections.NOTIFICATIONS).count, 0)

    def test_unread_rows_have_a_dot_read_rows_do_not(self):
        first = self.page.rows[0]
        self.assertIsNotNone(first._dot)
        self.buttons("Прочитать все")[0].invoke()
        self.settle()
        self.assertTrue(all(row._dot is None for row in self.page.rows))


class HistoryTest(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.db.execute("UPDATE history SET created_at = datetime('now','localtime')")
        self.db.execute(
            "UPDATE history SET created_at = ? WHERE action = ?",
            (
                (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S"),
                HistoryAction.PRODUCT_ADDED,
            ),
        )
        self.open(sections.HISTORY)

    @property
    def history(self) -> HistoryScreen:
        return self.page

    def descriptions(self) -> List[str]:
        return [r.description for r in self.history._records()]

    def test_default_period_is_week(self):
        for description in self.descriptions():
            self.assertNotIn("добавлен в аптечку", description)

    def test_all_time_shows_old_records(self):
        self.history._on_period(periods.ALL_TIME)
        self.assertTrue(any("добавлен в аптечку" in d for d in self.descriptions()))

    def test_action_filter(self):
        self.history._on_period(periods.ALL_TIME)
        self.history._on_action(HistoryAction.PRODUCT_ADDED)
        records = self.history._records()
        self.assertTrue(records)
        self.assertEqual({r.action for r in records}, {HistoryAction.PRODUCT_ADDED})

    def test_selects_apply_their_values(self):
        self.history.action_select._pick(HistoryAction.PRODUCT_ADDED)
        self.history.period_select._pick(periods.ALL_TIME)
        self.assertEqual(len(self.history.event_rows), len(self.history._records()))

    def test_search_by_product_name(self):
        self.history._on_period(periods.ALL_TIME)
        self.history._search.set("ПАРАЦЕТАМОЛ")
        self.history._apply_search()
        self.assertTrue(self.descriptions())
        for description in self.descriptions():
            self.assertIn("парацетамол", description.casefold())

    def test_nothing_found_message(self):
        self.history._search.set("zzzz")
        self.history._apply_search()
        self.settle()
        texts = [w.text() for w in find_all(self.history, QLabel)]
        self.assertIn("Записей нет", texts)

    def test_groups_are_titled_by_day(self):
        self.assertIn(day_title(date.today()), self.history.day_titles)

    def test_event_shows_time_and_title(self):
        texts = [w.text() for w in find_all(self.history, QLabel)]
        self.assertTrue(
            any(t in texts for t in ("Изменение товара", "Удаление товара"))
        )
        self.assertTrue(any(len(t) == 5 and t[2] == ":" for t in texts))

    def test_pending_search_is_harmless_when_the_screen_closes(self):
        self.history._on_search()
        self.assertTrue(self.history._timer.isActive())
        self.open(sections.HOME)


class ScrollAreaTest(WidgetTestCase):
    def make(self, content_height: int) -> ScrollArea:
        self.root.resize(300, 200)
        area = ScrollArea(parent=self.root)
        area.resize(300, 200)
        content = QWidget()
        content.setFixedHeight(content_height)
        area.body.addWidget(content)
        area.show()
        self.settle()
        return area

    def test_short_content_does_not_scroll(self):
        area = self.make(50)
        self.assertEqual(area.verticalScrollBar().maximum(), 0)

    def test_long_content_scrolls(self):
        area = self.make(600)
        bar = area.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(30)
        self.assertEqual(bar.value(), 30)

    def test_cannot_scroll_past_the_end(self):
        area = self.make(300)
        bar = area.verticalScrollBar()
        bar.setValue(10_000)
        self.assertEqual(bar.value(), bar.maximum())

    def test_wheel_step_is_a_few_lines(self):
        area = self.make(600)
        self.assertEqual(area.verticalScrollBar().singleStep(), 14)

    def test_scroll_to_top(self):
        area = self.make(600)
        area.verticalScrollBar().setValue(80)
        area.scroll_to_top()
        self.assertEqual(area.verticalScrollBar().value(), 0)

    def test_no_horizontal_bar(self):
        area = self.make(600)
        self.assertFalse(area.horizontalScrollBar().isVisible())
