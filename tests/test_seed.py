"""Тесты тестовых данных и работы с большим объёмом записей."""

import time

from pharmacy.db.seed import (
    DEMO_LOGIN,
    DEMO_PASSWORD,
    DEMO_PRODUCTS,
    seed_bulk,
    seed_demo,
    seed_full,
)
from pharmacy.utils.security import verify_password
from tests.helpers import DatabaseTestCase


class SeedDemoTest(DatabaseTestCase):
    """Демо-данные соответствуют макету."""

    def test_demo_data_created(self):
        user_id = seed_demo(self.db)
        self.assertIsNotNone(user_id)
        self.assertEqual(self.count_rows("users"), 1)
        self.assertEqual(self.count_rows("products"), len(DEMO_PRODUCTS))
        self.assertEqual(self.count_rows("shopping_list"), 4)
        self.assertGreaterEqual(self.count_rows("history"), 3)

    def test_demo_password_is_stored_as_hash(self):
        seed_demo(self.db)
        row = self.db.fetch_one(
            "SELECT password_hash FROM users WHERE login = ?", (DEMO_LOGIN,)
        )
        self.assertNotEqual(row["password_hash"], DEMO_PASSWORD)
        self.assertTrue(verify_password(DEMO_PASSWORD, row["password_hash"]))

    def test_second_run_does_not_duplicate(self):
        seed_demo(self.db)
        self.assertIsNone(seed_demo(self.db))
        self.assertEqual(self.count_rows("users"), 1)
        self.assertEqual(self.count_rows("products"), len(DEMO_PRODUCTS))

    def test_demo_has_expired_and_expiring_products(self):
        seed_demo(self.db)
        expired = self.db.fetch_one(
            "SELECT COUNT(*) AS n FROM products WHERE expiry_date < date('now')"
        )
        soon = self.db.fetch_one(
            "SELECT COUNT(*) AS n FROM products"
            " WHERE expiry_date BETWEEN date('now') AND date('now', '+30 days')"
        )
        self.assertGreaterEqual(expired["n"], 1)
        self.assertGreaterEqual(soon["n"], 2)


class BulkDataTest(DatabaseTestCase):
    """Требование ТЗ: корректная работа минимум с 1000 записями."""

    def test_thousand_products_listed_in_under_one_second(self):
        user_id = self.add_user()
        seed_bulk(self.db, user_id, count=1000)
        started = time.perf_counter()
        rows = self.db.fetch_all(
            "SELECT p.*, c.name AS category FROM products p"
            " JOIN categories c ON c.id = p.category_id"
            " WHERE p.user_id = ? ORDER BY p.expiry_date",
            (user_id,),
        )
        elapsed = time.perf_counter() - started
        self.assertEqual(len(rows), 1000)
        self.assertLess(elapsed, 1.0)

    def test_bulk_data_is_reproducible(self):
        user_id = self.add_user()
        seed_bulk(self.db, user_id, count=50, seed=7)
        first = [
            row["expiry_date"] for row in self.db.fetch_all("SELECT * FROM products")
        ]
        self.db.execute("DELETE FROM products")
        seed_bulk(self.db, user_id, count=50, seed=7)
        second = [
            row["expiry_date"] for row in self.db.fetch_all("SELECT * FROM products")
        ]
        self.assertEqual(first, second)


class SeedFullTest(DatabaseTestCase):
    """Полный набор покрывает все состояния, действия истории и уведомления."""

    def setUp(self) -> None:
        super().setUp()
        self.user_id = seed_demo(self.db)
        self.assertTrue(seed_full(self.db, self.user_id))

    def test_second_run_adds_nothing(self):
        before = self.count_rows("products")
        self.assertFalse(seed_full(self.db, self.user_id))
        self.assertEqual(self.count_rows("products"), before)

    def test_every_product_status_is_present(self):
        from pharmacy.services.container import build_services
        from pharmacy.services.status import ProductStatus

        views = build_services(self.db).products.list_products(self.user_id)
        seen = {status for view in views for status in view.statuses}
        self.assertEqual(seen, set(ProductStatus))
        self.assertTrue(any(len(v.statuses) > 1 for v in views))
        self.assertTrue(any(v.product.expiry_date is None for v in views))

    def test_every_category_and_unit_is_used(self):
        categories = self.db.fetch_one(
            "SELECT COUNT(DISTINCT category_id) AS n FROM products"
        )["n"]
        units = {r["unit"] for r in self.db.fetch_all("SELECT unit FROM products")}
        self.assertEqual(categories, 4)
        self.assertEqual(units, {"шт.", "упак.", "табл.", "мг", "г", "мл", "фл."})

    def test_every_history_action_is_present(self):
        actions = {r["action"] for r in self.db.fetch_all("SELECT action FROM history")}
        self.assertEqual(
            actions,
            {
                "product_added",
                "product_updated",
                "product_deleted",
                "shopping_added",
                "shopping_bought",
                "shopping_removed",
            },
        )

    def test_every_notification_kind_read_and_unread(self):
        rows = self.db.fetch_all("SELECT kind, is_read FROM notifications")
        self.assertEqual(
            {r["kind"] for r in rows}, {"expired", "expiring", "low_stock"}
        )
        self.assertEqual({r["is_read"] for r in rows}, {0, 1})

    def test_shopping_has_every_kind(self):
        rows = self.db.fetch_all(
            "SELECT source, is_bought, product_id FROM shopping_list"
        )
        self.assertEqual({r["source"] for r in rows}, {"manual", "notification"})
        self.assertEqual({r["is_bought"] for r in rows}, {0, 1})
        self.assertTrue(any(r["product_id"] is None for r in rows))
        self.assertTrue(any(r["product_id"] is not None for r in rows))
