"""Тесты схемы базы данных и менеджера подключения."""

import sqlite3

from pharmacy.db.schema import DEFAULT_CATEGORIES
from tests.helpers import DatabaseTestCase

EXPECTED_TABLES = {
    "users",
    "categories",
    "products",
    "notifications",
    "shopping_list",
    "history",
}

EXPECTED_INDEXES = {
    "idx_products_user",
    "idx_products_expiry",
    "idx_notifications_user_read",
    "idx_shopping_user_bought",
    "idx_history_user_created",
}


class SchemaTest(DatabaseTestCase):
    """Проверка, что схема создана так, как описано в ТЗ."""

    def test_all_tables_created(self):
        rows = self.db.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'")
        names = {row["name"] for row in rows}
        self.assertTrue(EXPECTED_TABLES.issubset(names))

    def test_indexes_created(self):
        rows = self.db.fetch_all("SELECT name FROM sqlite_master WHERE type = 'index'")
        names = {row["name"] for row in rows}
        self.assertTrue(EXPECTED_INDEXES.issubset(names))

    def test_default_categories_added(self):
        rows = self.db.fetch_all("SELECT name FROM categories")
        self.assertEqual({row["name"] for row in rows}, set(DEFAULT_CATEGORIES))

    def test_init_schema_twice_changes_nothing(self):
        self.db.init_schema()
        self.assertEqual(self.count_rows("categories"), len(DEFAULT_CATEGORIES))

    def test_foreign_keys_enabled(self):
        with self.db.transaction() as conn:
            enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(enabled, 1)

    def test_user_defaults(self):
        user_id = self.add_user()
        row = self.db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        self.assertEqual(row["warning_days"], 30)
        self.assertEqual(row["theme"], "system")
        self.assertEqual(row["notify_expired"], 1)
        self.assertEqual(row["notify_low_stock"], 1)
        self.assertTrue(row["created_at"])


class ConstraintTest(DatabaseTestCase):
    """Ограничения целостности: UNIQUE, CHECK, внешние ключи."""

    def test_login_must_be_unique(self):
        self.add_user("anna", "anna@example.com")
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_user("anna", "other@example.com")

    def test_email_must_be_unique(self):
        self.add_user("anna", "same@example.com")
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_user("boris", "same@example.com")

    def test_negative_quantity_rejected(self):
        user_id = self.add_user()
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_product(user_id, quantity=-1)

    def test_invalid_expiry_date_rejected(self):
        user_id = self.add_user()
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_product(user_id, expiry_date="2026-13-45")

    def test_missing_expiry_date_allowed(self):
        user_id = self.add_user()
        self.add_product(user_id, expiry_date=None)
        self.assertEqual(self.count_rows("products"), 1)

    def test_product_requires_existing_user(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.add_product(user_id=999)

    def test_invalid_theme_rejected(self):
        user_id = self.add_user()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE users SET theme = 'blue' WHERE id = ?", (user_id,))

    def test_category_in_use_cannot_be_deleted(self):
        user_id = self.add_user()
        self.add_product(user_id)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(
                "DELETE FROM categories WHERE id = ?", (self.category_id(),)
            )


class CascadeTest(DatabaseTestCase):
    """Правила удаления связанных данных."""

    def _fill_user_data(self):
        """Создаёт пользователя с товаром и записями во всех связанных таблицах."""
        user_id = self.add_user()
        product_id = self.add_product(user_id)
        self.db.execute(
            "INSERT INTO notifications (user_id, product_id, kind, message)"
            " VALUES (?, ?, 'low_stock', 'Мало')",
            (user_id, product_id),
        )
        self.db.execute(
            "INSERT INTO shopping_list (user_id, product_id, name) VALUES (?, ?, ?)",
            (user_id, product_id, "Ибупрофен"),
        )
        self.db.execute(
            "INSERT INTO history (user_id, product_id, action) VALUES (?, ?, ?)",
            (user_id, product_id, "product_added"),
        )
        return user_id, product_id

    def test_deleting_user_removes_all_his_data(self):
        user_id, _ = self._fill_user_data()
        self.db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        for table in ("products", "notifications", "shopping_list", "history"):
            self.assertEqual(self.count_rows(table), 0, table)

    def test_deleting_product_removes_its_notifications(self):
        _, product_id = self._fill_user_data()
        self.db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.assertEqual(self.count_rows("notifications"), 0)

    def test_deleting_product_keeps_history_and_shopping_rows(self):
        _, product_id = self._fill_user_data()
        self.db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        history = self.db.fetch_one("SELECT product_id FROM history")
        shopping = self.db.fetch_one("SELECT product_id FROM shopping_list")
        self.assertIsNone(history["product_id"])
        self.assertIsNone(shopping["product_id"])

    def test_shopping_item_without_product_allowed(self):
        user_id = self.add_user()
        self.db.execute(
            "INSERT INTO shopping_list (user_id, name, source) VALUES (?, ?, 'manual')",
            (user_id, "Пластыри"),
        )
        self.assertEqual(self.count_rows("shopping_list"), 1)


class TransactionTest(DatabaseTestCase):
    """Откат транзакции при ошибке."""

    def test_rollback_on_error(self):
        with self.assertRaises(RuntimeError):
            with self.db.transaction() as conn:
                conn.execute("INSERT INTO categories (name) VALUES ('Временная')")
                raise RuntimeError("сбой")
        row = self.db.fetch_one(
            "SELECT COUNT(*) AS n FROM categories WHERE name = ?", ("Временная",)
        )
        self.assertEqual(row["n"], 0)

    def test_query_parameters_are_not_executed_as_sql(self):
        self.add_user("anna")
        hostile = "x'; DROP TABLE users; --"
        found = self.db.fetch_one("SELECT id FROM users WHERE login = ?", (hostile,))
        self.assertIsNone(found)
        self.assertEqual(self.count_rows("users"), 1)


class CasefoldTest(DatabaseTestCase):
    """Поиск без учёта регистра для русских букв."""

    def fold(self, text):
        return self.db.fetch_one("SELECT casefold(?) AS value", (text,))["value"]

    def test_cyrillic_lowercased(self):
        self.assertEqual(self.fold("ИБУПРОФЕН"), "ибупрофен")

    def test_latin_lowercased(self):
        self.assertEqual(self.fold("Aspirin"), "aspirin")

    def test_null_stays_null(self):
        self.assertIsNone(self.fold(None))

    def test_builtin_like_cannot_do_it_but_casefold_can(self):
        user_id = self.add_user()
        self.add_product(user_id, name="Ибупрофен")
        plain_like = self.db.fetch_all(
            "SELECT id FROM products WHERE name LIKE ?", ("%ИБУ%",)
        )
        with_casefold = self.db.fetch_all(
            "SELECT id FROM products WHERE casefold(name) LIKE ?", ("%ибу%",)
        )
        self.assertEqual(len(plain_like), 0)
        self.assertEqual(len(with_casefold), 1)


class ShoppingMigrationTest(DatabaseTestCase):
    def test_old_shopping_table_is_rebuilt_with_data(self):
        with self.db.transaction() as conn:
            conn.execute("DROP TABLE shopping_list")
            conn.execute(
                "CREATE TABLE shopping_list (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " user_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,"
                " product_id INTEGER REFERENCES products (id) ON DELETE SET NULL,"
                " name TEXT NOT NULL, quantity REAL NOT NULL DEFAULT 1,"
                " unit TEXT NOT NULL DEFAULT 'шт.',"
                " source TEXT NOT NULL DEFAULT 'manual'"
                " CHECK (source IN ('manual', 'notification')),"
                " is_bought INTEGER NOT NULL DEFAULT 0,"
                " created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')))"
            )
        user_id = self.add_user("anna")
        self.db.execute(
            "INSERT INTO shopping_list (user_id, name, source)"
            " VALUES (?, 'Вата', 'manual')",
            (user_id,),
        )
        self.db.init_schema()
        self.assertEqual(self.count_rows("shopping_list"), 1)
        self.db.execute(
            "INSERT INTO shopping_list (user_id, name, source)"
            " VALUES (?, 'Бинт', 'kit')",
            (user_id,),
        )
        self.assertEqual(self.count_rows("shopping_list"), 2)
