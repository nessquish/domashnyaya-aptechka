"""Тесты экранов товаров: список, форма, карточка."""

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLabel

from pharmacy.db.seed import seed_bulk
from pharmacy.models import HistoryAction
from pharmacy.services.status import ProductStatus
from pharmacy.ui import sections
from pharmacy.ui.screens.my_kit import PAGE_SIZE, MyKitScreen
from pharmacy.ui.screens.product_card import ProductCardDialog, _days_phrase
from pharmacy.ui.screens.product_form import ProductFormDialog
from pharmacy.ui.widgets.badge import Badge
from tests.qt_helpers import ShellTestCase, click, find_all


class KitTestCase(ShellTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.open(sections.MY_KIT)

    @property
    def kit(self) -> MyKitScreen:
        return self.page

    def names(self) -> List[str]:
        return [row[0] for row in self.kit.table.row_texts]

    def product_id(self, name: str) -> int:
        views = self.services.products.list_products(self.app.user.id)
        return next(v.product.id for v in views if v.product.name == name)


class MyKitTest(KitTestCase):
    def test_shows_all_products_sorted_by_state_by_default(self):
        names = self.names()
        self.assertEqual(len(names), 8)
        self.assertEqual(names[0], "Активированный уголь")  # просрочен
        self.assertEqual(names[-1], "Зубная паста")  # норма с самым поздним сроком

    def test_row_has_a_cell_for_every_column(self):
        for row in self.kit.table.row_texts:
            self.assertEqual(len(row), 8)

    def test_search_ignores_case(self):
        self.kit._search_field.set("ИБУ")
        self.kit._apply_search()
        self.assertEqual(self.names(), ["Ибупрофен"])

    def test_typing_in_search_filters_after_a_pause(self):
        self.kit._search_field.entry.setText("ибу")
        self.kit._search_field.entry.textEdited.emit("ибу")
        self.assertTrue(self.kit._search_timer.isActive())
        self.kit._search_timer.timeout.emit()
        self.assertEqual(self.names(), ["Ибупрофен"])

    def test_nothing_found_message(self):
        self.kit._search_field.set("zzz")
        self.kit._apply_search()
        self.settle()
        self.assertEqual(self.names(), [])
        texts = [w.text() for w in find_all(self.kit, QLabel)]
        self.assertIn("Ничего не найдено", texts)
        self.assertIn("Показано 0 из 0", texts)

    def test_category_filter(self):
        category = self.services.products.list_categories()[0].id
        self.kit._on_category(category)
        shown = self.kit.table.row_texts
        self.assertTrue(shown)
        for row in shown:
            self.assertEqual(row[2], "Лекарства")

    def test_status_filter(self):
        self.kit._on_status(ProductStatus.EXPIRED)
        self.assertEqual(self.names(), ["Активированный уголь"])

    def test_filters_are_in_the_toolbar_and_apply(self):
        self.kit.status_select._pick(ProductStatus.EXPIRED)
        self.assertEqual(self.names(), ["Активированный уголь"])
        self.assertEqual(self.kit.status_select.get(), ProductStatus.EXPIRED)

    def test_pagination(self):
        seed_bulk(self.db, self.app.user.id, count=20)
        self.open(sections.MY_KIT)
        self.assertEqual(len(self.names()), PAGE_SIZE)
        first = self.names()
        self.kit._on_page(2)
        self.assertEqual(len(self.names()), PAGE_SIZE)
        self.assertNotEqual(self.names(), first)
        self.kit._on_page(4)
        self.assertEqual(len(self.names()), 28 - 3 * PAGE_SIZE)

    def test_pagination_buttons_change_the_page(self):
        seed_bulk(self.db, self.app.user.id, count=20)
        self.open(sections.MY_KIT)
        pagination = self.kit.pagination
        click(pagination, pagination.cell_left(2) + 5, 10)  # кнопка «2»
        self.settle()
        self.assertEqual(self.kit._page, 2)

    def test_page_resets_after_filter(self):
        seed_bulk(self.db, self.app.user.id, count=20)
        self.open(sections.MY_KIT)
        self.kit._on_page(3)
        self.kit._search_field.set("ибу")
        self.kit._apply_search()
        self.assertEqual(self.kit._page, 1)

    def test_summary_counts_shown_rows(self):
        self.assertEqual(self.kit.summary.text(), "Показано 1–8 из 8")

    def test_product_name_opens_card(self):
        first = self.kit.table.cell_widgets(0)[0]
        click(first)
        self.settle()
        self.assertEqual(len(find_all(self.app, ProductCardDialog)), 1)
        self.assertIsInstance(self.page, MyKitScreen)

    def test_add_button_opens_the_dialog_on_the_same_screen(self):
        self.buttons("Добавить товар в аптечку")[0].invoke()
        self.settle()
        self.assertIsInstance(self.page, MyKitScreen)  # на другой экран не уходим
        self.assertEqual(len(find_all(self.app, ProductFormDialog)), 1)

    def test_empty_state_for_new_account(self):
        self.db.execute("DELETE FROM products")
        self.open(sections.MY_KIT)
        texts = [w.text() for w in find_all(self.kit, QLabel)]
        self.assertIn("В аптечке пока пусто", texts)
        self.assertFalse(hasattr(self.kit, "_table"))
        self.buttons("Добавить товар в аптечку")[0].invoke()
        self.settle()
        self.assertEqual(len(find_all(self.app, ProductFormDialog)), 1)

    def test_pending_search_is_harmless_when_the_screen_closes(self):
        self.kit._on_search()
        self.assertTrue(self.kit._search_timer.isActive())
        self.open(sections.HOME)

    def test_table_columns_line_up(self):
        lefts = {
            tuple(
                cell.mapTo(self.kit, cell.rect().topLeft()).x()
                for cell in self.kit.table.cell_widgets(0)
            )
        }
        self.assertEqual(len(next(iter(lefts))), 8)
        self.assertEqual(len(set(next(iter(lefts)))), 1)


class ProductEditTest(KitTestCase):
    """Редактирование товара: окно поверх текущего экрана."""

    def edit(self, product="Ибупрофен") -> ProductFormDialog:
        self.shell.edit_product(self.product_id(product))
        self.settle()
        return find_all(self.app, ProductFormDialog)[0]

    def dialogs(self):
        return find_all(self.app, ProductFormDialog)

    def fill(self, form, **values):
        for key, value in values.items():
            form.fields[key].set(value)

    def test_edit_opens_over_the_current_screen(self):
        dialog = self.edit()
        self.assertTrue(dialog.editing)
        self.assertIsInstance(self.page, MyKitScreen)
        self.assertFalse(dialog.isWindow())

    def test_edit_prefills_all_fields(self):
        data = self.edit().read_form()
        self.assertEqual(data.name, "Ибупрофен")
        self.assertEqual(data.quantity, "2")
        self.assertEqual(data.min_quantity, "3")
        self.assertEqual(data.storage_place, "Шкаф")
        self.assertRegex(data.expiry_date, r"^\d\d\.\d\d\.\d{4}$")
        self.assertTrue(data.category_id)

    def test_added_date_shows_when_the_product_was_added(self):
        dialog = self.edit()
        self.assertRegex(dialog.added_field.get(), r"^\d\d\.\d\d\.\d{4}$")
        self.assertTrue(dialog.added_field.entry.isReadOnly())

    def test_titles_and_button_say_editing(self):
        dialog = self.edit()
        self.assertEqual(dialog.save_button.text(), "Сохранить изменения")

    def test_edit_saves_closes_and_shows_the_card_again(self):
        dialog = self.edit()
        self.fill(dialog, quantity="10")
        dialog.save_button.invoke()
        self.settle()
        self.assertEqual(self.dialogs(), [])
        card = find_all(self.app, ProductCardDialog)
        self.assertEqual(len(card), 1)
        self.assertIn("10 упак.", [w.text() for w in find_all(card[0], QLabel)])
        view = self.services.products.get_product(
            self.app.user.id, self.product_id("Ибупрофен")
        )
        self.assertEqual(view.product.quantity, 10)
        actions = [
            r.action for r in self.services.history.list_history(self.app.user.id)
        ]
        self.assertIn(HistoryAction.PRODUCT_UPDATED, actions)

    def test_table_underneath_is_refreshed_after_saving(self):
        dialog = self.edit()
        self.fill(dialog, name="Нурофен")
        dialog.save_button.invoke()
        self.settle()
        self.assertIn("Нурофен", self.names())
        self.assertNotIn("Ибупрофен", self.names())

    def test_empty_name_shows_error_and_disables_save(self):
        dialog = self.edit()
        self.fill(dialog, name="")
        dialog.save_button.invoke()
        self.assertEqual(dialog.fields["name"].error, "Введите название")
        self.assertFalse(dialog.save_button.enabled)
        self.assertEqual(len(self.dialogs()), 1)

    def test_bad_values_are_marked_on_their_fields(self):
        for key, value in {
            "quantity": "abc",
            "min_quantity": "-1",
            "expiry_date": "31.31.2030",
        }.items():
            dialog = self.edit()
            self.fill(dialog, **{key: value})
            dialog.save_button.invoke()
            self.assertIsNotNone(dialog.fields[key].error, key)
            dialog.close_modal()
            self.settle()

    def test_typing_after_error_reenables_save(self):
        dialog = self.edit()
        self.fill(dialog, name="")
        dialog.save_button.invoke()
        dialog.fields["name"].entry.textEdited.emit("А")
        self.assertTrue(dialog.save_button.enabled)

    def test_cancel_closes_and_returns_to_the_card(self):
        dialog = self.edit()
        dialog.cancel_button.invoke()
        self.settle()
        self.assertEqual(self.dialogs(), [])
        self.assertEqual(len(find_all(self.app, ProductCardDialog)), 1)

    def test_nothing_is_saved_on_cancel(self):
        dialog = self.edit()
        self.fill(dialog, quantity="99")
        dialog.cancel_button.invoke()
        view = self.services.products.get_product(
            self.app.user.id, self.product_id("Ибупрофен")
        )
        self.assertEqual(view.product.quantity, 2)

    def test_editing_a_deleted_product_does_not_crash(self):
        dialog = self.edit()
        self.services.products.delete_product(
            self.app.user.id, self.product_id("Ибупрофен")
        )
        dialog.save_button.invoke()
        self.settle()
        self.assertEqual(self.dialogs(), [])

    def test_editing_a_missing_product_opens_nothing(self):
        self.shell.edit_product(99999)
        self.settle()
        self.assertEqual(self.dialogs(), [])

    def test_add_flow_still_uses_the_same_window(self):
        self.shell.add_product()
        self.settle()
        self.assertFalse(self.dialogs()[0].editing)


class ProductCardTest(KitTestCase):
    """Карточка товара: окно поверх текущего экрана."""

    def open_card(self, name="Ибупрофен") -> ProductCardDialog:
        self.shell.open_product(self.product_id(name))
        self.settle()
        return find_all(self.app, ProductCardDialog)[0]

    def texts(self, widget):
        return [w.text() for w in find_all(widget, QLabel)]

    def test_card_opens_over_the_current_screen(self):
        card = self.open_card()
        self.assertIsInstance(self.page, MyKitScreen)
        self.assertFalse(card.isWindow())
        self.assertIs(card.parentWidget(), self.app)

    def test_shows_product_data(self):
        texts = self.texts(self.open_card())
        self.assertIn("Ибупрофен", texts)
        self.assertIn("2 упак.", texts)
        self.assertIn("3 упак.", texts)
        self.assertIn("Шкаф", texts)
        self.assertIn("Жаропонижающее, обезболивающее", texts)

    def test_empty_fields_show_no_data(self):
        texts = self.texts(self.open_card("Бинт"))
        self.assertGreaterEqual(texts.count("Нет данных"), 2)

    def test_days_left_is_shown_for_expiring_product(self):
        self.assertTrue(any("через" in t for t in self.texts(self.open_card())))

    def test_status_badges_are_shown(self):
        card = self.open_card("Активированный уголь")
        names = [b.text for b in find_all(card, Badge)]
        self.assertIn("Просрочен", names)

    def test_close_button_and_escape_close_the_card(self):
        card = self.open_card()
        click(card.close_button)
        self.settle()
        self.assertEqual(find_all(self.app, ProductCardDialog), [])
        card = self.open_card()
        QTest.keyClick(card, Qt.Key.Key_Escape)
        self.settle()
        self.assertEqual(find_all(self.app, ProductCardDialog), [])

    def test_add_to_shopping_list(self):
        card = self.open_card("Витамин D")
        card.list_button.invoke()
        self.settle()
        self.assertTrue(
            self.services.shopping.is_in_list(
                self.app.user.id, self.product_id("Витамин D")
            )
        )
        cards = find_all(self.app, ProductCardDialog)
        self.assertEqual(len(cards), 1)  # карточка открыта заново, уже с отметкой
        self.assertTrue(cards[0].list_button.enabled)
        self.assertEqual(cards[0].list_button.text(), "Добавить ещё в список")
        item = next(
            i
            for i in self.services.shopping.list_items(self.app.user.id)
            if i.name == "Витамин D"
        )
        self.assertEqual((item.source, item.quantity), ("card", 1))
        cards[0].list_button.invoke()  # ещё раз: количество растёт
        self.settle()
        again = [
            i
            for i in self.services.shopping.list_items(self.app.user.id)
            if i.name == "Витамин D"
        ]
        self.assertEqual([i.quantity for i in again], [2])

    def test_edit_button_opens_the_edit_window(self):
        card = self.open_card()
        card.edit_button.invoke()
        self.settle()
        self.assertEqual(find_all(self.app, ProductCardDialog), [])
        forms = find_all(self.app, ProductFormDialog)
        self.assertEqual(len(forms), 1)
        self.assertTrue(forms[0].editing)

    def test_delete_asks_confirmation(self):
        card = self.open_card()
        card.delete_button.invoke()
        self.settle()
        cancel = self.buttons("Отмена")[0]
        cancel.invoke()
        self.settle()
        self.assertEqual(len(self.names_in_db()), 8)
        self.assertEqual(len(find_all(self.app, ProductCardDialog)), 1)

    def test_confirmed_delete_removes_product_and_refreshes_the_table(self):
        card = self.open_card()
        card.delete_button.invoke()
        self.settle()
        confirm = [b for b in self.buttons("Удалить") if b._variant == "danger_solid"]
        confirm[0].invoke()
        self.settle()
        self.assertEqual(find_all(self.app, ProductCardDialog), [])
        self.assertIsInstance(self.page, MyKitScreen)
        self.assertEqual(len(self.names_in_db()), 7)
        self.assertNotIn("Ибупрофен", self.names())

    def test_card_and_edit_window_fit_into_the_window_at_every_text_size(self):
        for size in ("normal", "medium", "large"):
            self.shell.set_text_size(size)
            self.settle()
            self.open(sections.MY_KIT)
            for opener in (self.shell.open_product, self.shell.edit_product):
                opener(self.product_id("Ибупрофен"))
                self.settle()
                dialog = (
                    find_all(self.app, ProductCardDialog)
                    or find_all(self.app, ProductFormDialog)
                )[0]
                card = dialog.card
                self.assertGreaterEqual(card.y(), 0, size)
                self.assertLessEqual(card.y() + card.height(), self.app.height(), size)
                self.assertLessEqual(card.x() + card.width(), self.app.width(), size)
                dialog.close_modal()
                self.settle()

    def test_missing_product_opens_nothing(self):
        self.shell.open_product(99999)
        self.settle()
        self.assertEqual(find_all(self.app, ProductCardDialog), [])

    def names_in_db(self):
        return self.services.products.list_products(self.app.user.id)

    def test_days_phrase(self):
        self.assertEqual(_days_phrase(19), "через 19 дней")
        self.assertEqual(_days_phrase(1), "через 1 день")
        self.assertEqual(_days_phrase(0), "истекает сегодня")
        self.assertEqual(_days_phrase(-3), "просрочено на 3 дня")
