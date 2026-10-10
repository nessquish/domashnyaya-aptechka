"""Схема базы данных (по ER-диаграмме из технического задания).

Здесь только описание таблиц, ограничений и индексов. Подключением к базе
занимается ``pharmacy.db.connection.Database``.
"""

# Категории товаров, которые добавляются в справочник при создании базы.
DEFAULT_CATEGORIES = (
    "Лекарства",
    "Медицинские товары",
    "Бытовая химия",
    "Средства гигиены",
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL UNIQUE,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    warning_days INTEGER NOT NULL DEFAULT 30
        CHECK (warning_days BETWEEN 1 AND 365),
    theme TEXT NOT NULL DEFAULT 'system'
        CHECK (theme IN ('light', 'dark', 'system')),
    notify_expired INTEGER NOT NULL DEFAULT 1
        CHECK (notify_expired IN (0, 1)),
    notify_low_stock INTEGER NOT NULL DEFAULT 1
        CHECK (notify_low_stock IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL
        REFERENCES users (id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL
        REFERENCES categories (id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    unit TEXT NOT NULL DEFAULT 'шт.',
    expiry_date TEXT
        CHECK (expiry_date IS NULL OR date(expiry_date) IS NOT NULL),
    indications TEXT,
    storage_place TEXT,
    min_quantity REAL NOT NULL DEFAULT 0 CHECK (min_quantity >= 0),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL
        REFERENCES users (id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL
        REFERENCES products (id) ON DELETE CASCADE,
    kind TEXT NOT NULL
        CHECK (kind IN ('expired', 'expiring', 'low_stock')),
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0 CHECK (is_read IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS shopping_list (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL
        REFERENCES users (id) ON DELETE CASCADE,
    product_id INTEGER
        REFERENCES products (id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit TEXT NOT NULL DEFAULT 'шт.',
    source TEXT NOT NULL DEFAULT 'manual'
        CHECK (source IN ('manual', 'notification')),
    is_bought INTEGER NOT NULL DEFAULT 0 CHECK (is_bought IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL
        REFERENCES users (id) ON DELETE CASCADE,
    product_id INTEGER
        REFERENCES products (id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_products_user
    ON products (user_id);
CREATE INDEX IF NOT EXISTS idx_products_expiry
    ON products (expiry_date);
CREATE INDEX IF NOT EXISTS idx_notifications_user_read
    ON notifications (user_id, is_read);
CREATE INDEX IF NOT EXISTS idx_shopping_user_bought
    ON shopping_list (user_id, is_bought);
CREATE INDEX IF NOT EXISTS idx_history_user_created
    ON history (user_id, created_at);
"""
