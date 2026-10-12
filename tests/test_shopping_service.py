"""Тесты списка покупок."""

from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.models import HistoryAction, ShoppingSource
from pharmacy.services.shopping_service import ShoppingService
from tests.helpers import DatabaseTestCase


class ShoppingTestCase(DatabaseTestCase):
    """База, сервис списка покупок и пользователь anna."""

    def setUp(self) -> None:
        super().setUp()
        self.service = ShoppingService(self.db)
        self.user_id = self.add_user("anna")

    def history_actions(self, user_id=None):
        rows = self.db.fetch_all(
            "SELECT action FROM history WHERE user_id = ? ORDER BY id",
            (user_id or self.user_id,),
        )
        return [row["action"] for row in rows]


class AddManualTest(ShoppingTestCase):
    """Ручное добавление позиции."""

    def test_adds_item_with_defaults(self):
        item = self.service.add_manual(self.user_id, "  Бинт  ")
        self.assertEqual(item.name, "Бинт")
        self.assertEqual(item.quantity, 1)
        self.assertEqual(item.unit, "шт.")
        self.assertEqual(item.source, ShoppingSource.MANUAL)
        self.assertIsNone(item.product_id)
        self.assertFalse(item.is_bought)

    def test_accepts_quantity_with_comma_and_unit(self):
        item = self.service.add_manual(self.user_id, "Вата", "1,5", "упак.")
        self.assertEqual((item.quantity, item.unit), (1.5, "упак."))

    def test_empty_name_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.service.add_manual(self.user_id, "   ")
        self.assertEqual(ctx.exception.field, "name")

    def test_too_long_name_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.service.add_manual(self.user_id, "а" * 101)
        self.assertEqual(ctx.exception.field, "name")

    def test_bad_quantities_are_rejected(self):
        for text in ("0", "-2", "abc", "1e999", "2000000"):
            with self.assertRaises(ValidationError, msg=text) as ctx:
                self.service.add_manual(self.user_id, "Бинт", text)
            self.assertEqual(ctx.exception.field, "quantity", text)
        self.assertEqual(self.count_rows("shopping_list"), 0)

    def test_writes_history(self):
        self.service.add_manual(self.user_id, "Бинт", "2", "упак.")
        row = self.db.fetch_one("SELECT * FROM history")
        self.assertEqual(row["action"], HistoryAction.SHOPPING_ADDED)
        self.assertEqual(
            row["description"], "Бинт · 2 упак. · добавлено в список покупок"
        )


class AddFromProductTest(ShoppingTestCase):
    """Добавление товара из аптечки."""

    def make_product(self, quantity=1, min_quantity=3):
        return self.db.execute(
            "INSERT INTO products (user_id, category_id, name, quantity, unit,"
            " min_quantity) VALUES (?, ?, 'Ибупрофен', ?, 'упак.', ?)",
            (self.user_id, self.category_id(), quantity, min_quantity),
        )

    def test_default_quantity_tops_up_to_double_minimum(self):
        item = self.service.add_from_product(self.user_id, self.make_product(1, 3))
        self.assertEqual(item.quantity, 5)
        self.assertEqual(item.unit, "упак.")
        self.assertEqual(item.source, ShoppingSource.NOTIFICATION)

    def test_default_quantity_is_at_least_one(self):
        item = self.service.add_from_product(self.user_id, self.make_product(10, 1))
        self.assertEqual(item.quantity, 1)

    def test_explicit_quantity(self):
        item = self.service.add_from_product(
            self.user_id, self.make_product(), quantity="4"
        )
        self.assertEqual(item.quantity, 4)

    def test_bad_explicit_quantity(self):
        with self.assertRaises(ValidationError):
            self.service.add_from_product(
                self.user_id, self.make_product(), quantity="0"
            )

    def test_adding_again_increases_the_quantity(self):
        product_id = self.make_product()
        first = self.service.add_from_product(
            self.user_id, product_id, source=ShoppingSource.KIT
        )
        again = self.service.add_from_product(
            self.user_id, product_id, source=ShoppingSource.KIT
        )
        self.assertEqual(self.count_rows("shopping_list"), 1)
        self.assertEqual((first.quantity, again.quantity), (1, 2))
        third = self.service.add_from_product(self.user_id, product_id, "3")
        self.assertEqual(third.quantity, 5)

    def test_quantity_does_not_depend_on_the_stock_in_the_kit(self):
        product_id = self.make_product(quantity=1, min_quantity=50)
        item = self.service.add_from_product(
            self.user_id, product_id, source=ShoppingSource.KIT
        )
        self.assertEqual(item.quantity, 1)

    def test_source_follows_the_place_of_adding(self):
        for source in (
            ShoppingSource.KIT,
            ShoppingSource.CARD,
            ShoppingSource.HOME,
            ShoppingSource.NOTIFICATION,
        ):
            product_id = self.make_product()
            item = self.service.add_from_product(
                self.user_id, product_id, source=source
            )
            self.assertEqual(item.source, source)

    def test_bulk_add_counts_new_and_increased(self):
        first, second = self.make_product(), self.make_product()
        self.service.add_from_product(self.user_id, first, source=ShoppingSource.KIT)
        created, increased = self.service.add_products(self.user_id, [first, second])
        self.assertEqual((created, increased), (1, 1))
        self.assertEqual(self.count_rows("shopping_list"), 2)

    def test_manual_add_of_a_known_product_increases_it(self):
        product_id = self.make_product()
        self.service.add_from_product(self.user_id, product_id, source="kit")
        item = self.service.add_manual(
            self.user_id, "Ибупрофен", "2", "упак.", product_id
        )
        self.assertEqual(item.quantity, 3)
        self.assertEqual(self.count_rows("shopping_list"), 1)

    def test_can_add_again_after_purchase(self):
        product_id = self.make_product()
        first = self.service.add_from_product(self.user_id, product_id)
        self.service.set_bought(self.user_id, first.id)
        self.service.add_from_product(self.user_id, product_id)
        self.assertEqual(self.count_rows("shopping_list"), 2)

    def test_is_in_list_follows_purchase(self):
        product_id = self.make_product()
        self.assertFalse(self.service.is_in_list(self.user_id, product_id))
        item = self.service.add_from_product(self.user_id, product_id)
        self.assertTrue(self.service.is_in_list(self.user_id, product_id))
        self.service.set_bought(self.user_id, item.id)
        self.assertFalse(self.service.is_in_list(self.user_id, product_id))

    def test_unknown_product(self):
        with self.assertRaises(NotFoundError):
            self.service.add_from_product(self.user_id, 999)

    def test_other_users_product_is_not_available(self):
        other_id = self.add_user("boris")
        product_id = self.add_product(other_id)
        with self.assertRaises(NotFoundError):
            self.service.add_from_product(self.user_id, product_id)

    def test_item_survives_product_deletion(self):
        product_id = self.make_product()
        item = self.service.add_from_product(self.user_id, product_id)
        self.db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        kept = self.service.list_items(self.user_id)
        self.assertEqual([i.id for i in kept], [item.id])
        self.assertIsNone(kept[0].product_id)


class StatusAndRemovalTest(ShoppingTestCase):
    """Отметка «куплено», удаление, очистка."""

    def setUp(self) -> None:
        super().setUp()
        self.first = self.service.add_manual(self.user_id, "Бинт")
        self.second = self.service.add_manual(self.user_id, "Вата")

    def test_mark_bought_and_back(self):
        item = self.service.set_bought(self.user_id, self.first.id)
        self.assertTrue(item.is_bought)
        item = self.service.set_bought(self.user_id, self.first.id, False)
        self.assertFalse(item.is_bought)

    def test_purchase_is_written_to_history_once(self):
        self.service.set_bought(self.user_id, self.first.id)
        self.service.set_bought(self.user_id, self.first.id)
        self.assertEqual(self.history_actions().count(HistoryAction.SHOPPING_BOUGHT), 1)

    def test_unmarking_is_not_written_to_history(self):
        self.service.set_bought(self.user_id, self.first.id)
        self.service.set_bought(self.user_id, self.first.id, False)
        self.assertEqual(self.history_actions().count(HistoryAction.SHOPPING_BOUGHT), 1)

    def test_bought_items_go_to_the_bottom(self):
        self.service.set_bought(self.user_id, self.second.id)
        names = [i.name for i in self.service.list_items(self.user_id)]
        self.assertEqual(names, ["Бинт", "Вата"])
        self.service.set_bought(self.user_id, self.first.id)
        self.service.set_bought(self.user_id, self.second.id, False)
        names = [i.name for i in self.service.list_items(self.user_id)]
        self.assertEqual(names, ["Вата", "Бинт"])

    def test_list_filters(self):
        self.service.set_bought(self.user_id, self.first.id)
        self.assertEqual(len(self.service.list_items(self.user_id)), 2)
        self.assertEqual(
            [i.name for i in self.service.list_items(self.user_id, False)], ["Вата"]
        )
        self.assertEqual(
            [i.name for i in self.service.list_items(self.user_id, True)], ["Бинт"]
        )

    def test_remove_writes_history(self):
        self.service.remove(self.user_id, self.first.id)
        self.assertEqual(self.count_rows("shopping_list"), 1)
        self.assertEqual(
            self.history_actions().count(HistoryAction.SHOPPING_REMOVED), 1
        )

    def test_clear_bought_keeps_open_items(self):
        self.service.set_bought(self.user_id, self.first.id)
        self.assertEqual(self.service.clear_bought(self.user_id), 1)
        names = [i.name for i in self.service.list_items(self.user_id)]
        self.assertEqual(names, ["Вата"])

    def test_unknown_item(self):
        with self.assertRaises(NotFoundError):
            self.service.set_bought(self.user_id, 999)
        with self.assertRaises(NotFoundError):
            self.service.remove(self.user_id, 999)

    def test_other_user_cannot_touch_my_list(self):
        other_id = self.add_user("boris")
        with self.assertRaises(NotFoundError):
            self.service.set_bought(other_id, self.first.id)
        with self.assertRaises(NotFoundError):
            self.service.remove(other_id, self.first.id)
        self.assertEqual(self.service.list_items(other_id), [])
        self.assertEqual(self.service.clear_bought(other_id), 0)
        self.assertEqual(self.count_rows("shopping_list"), 2)
