"""Тестовые данные для демонстрации и проверки приложения.

Запуск из консоли::

    python -m pharmacy.db.seed              # демо-пользователь и товары
    python -m pharmacy.db.seed --bulk 1000  # плюс 1000 товаров для проверки скорости
    python -m pharmacy.db.seed --full       # демо-пользователь со всеми видами данных
    python -m pharmacy.db.seed --reset      # удалить файл базы и создать заново
"""

import argparse
import random
from datetime import date, timedelta
from typing import Optional, Sequence

from pharmacy.db.connection import Database
from pharmacy.utils.security import hash_password

DEMO_LOGIN = "nessquish"
DEMO_USERNAME = "Анастасия"
DEMO_EMAIL = "nessquish@mail.ru"
DEMO_PASSWORD = "demo12345"

# Товары из макета Figma. Срок годности задан числом дней от сегодняшней даты,
# чтобы после запуска всегда были и просроченные, и скоро истекающие товары.
# (название, категория, количество, единица, дней до конца срока или None,
#  место хранения, минимальный остаток, показания)
DEMO_PRODUCTS = (
    ("Активированный уголь", "Лекарства", 1, "упак.", -47, "Шкаф", 2, "Сорбент"),
    (
        "Ибупрофен",
        "Лекарства",
        2,
        "упак.",
        19,
        "Шкаф",
        3,
        "Жаропонижающее, обезболивающее",
    ),
    ("Витамин D", "Лекарства", 1, "упак.", 24, "Кухня", 1, "Витамины"),
    ("Хлоргексидин", "Медицинские товары", 1, "фл.", 120, "Аптечка", 1, "Антисептик"),
    (
        "Парацетамол",
        "Лекарства",
        10,
        "упак.",
        220,
        "Шкаф",
        3,
        "Жаропонижающее, болеутоляющее",
    ),
    ("Зубная паста", "Средства гигиены", 2, "шт.", 250, "Ванная", 1, ""),
    ("Средство для посуды", "Бытовая химия", 1, "шт.", 520, "Кухня", 1, ""),
    ("Бинт", "Медицинские товары", 1, "шт.", None, "Аптечка", 2, ""),
)


def _expiry_from_today(days: Optional[int]) -> Optional[str]:
    """Возвращает дату через ``days`` дней от сегодня в формате ГГГГ-ММ-ДД."""
    if days is None:
        return None
    return (date.today() + timedelta(days=days)).isoformat()


def _timestamp(days_ago: int, time_text: str) -> str:
    """Возвращает отметку времени «``days_ago`` дней назад в указанное время»."""
    day = date.today() - timedelta(days=days_ago)
    return f"{day.isoformat()} {time_text}"


def seed_demo(db: Database) -> Optional[int]:
    """Добавляет демо-пользователя, его товары, список покупок и историю.

    Args:
        db: Менеджер базы данных с уже созданной схемой.

    Returns:
        Идентификатор созданного пользователя или None, если демо-пользователь
        уже есть в базе (повторный запуск ничего не дублирует).
    """
    if db.fetch_one("SELECT id FROM users WHERE login = ?", (DEMO_LOGIN,)):
        return None
    categories = {
        row["name"]: row["id"]
        for row in db.fetch_all("SELECT id, name FROM categories")
    }
    with db.transaction() as conn:
        user_id = conn.execute(
            "INSERT INTO users (login, username, email, password_hash)"
            " VALUES (?, ?, ?, ?)",
            (DEMO_LOGIN, DEMO_USERNAME, DEMO_EMAIL, hash_password(DEMO_PASSWORD)),
        ).lastrowid
        product_ids = {}
        for (
            name,
            category,
            quantity,
            unit,
            days,
            place,
            minimum,
            notes,
        ) in DEMO_PRODUCTS:
            product_ids[name] = conn.execute(
                "INSERT INTO products (user_id, category_id, name, quantity, unit,"
                " expiry_date, storage_place, min_quantity, indications)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    categories[category],
                    name,
                    quantity,
                    unit,
                    _expiry_from_today(days),
                    place,
                    minimum,
                    notes,
                ),
            ).lastrowid
        conn.executemany(
            "INSERT INTO shopping_list (user_id, product_id, name, quantity, unit,"
            " source, is_bought, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    user_id,
                    product_ids["Ибупрофен"],
                    "Ибупрофен",
                    2,
                    "упак.",
                    "notification",
                    0,
                    _timestamp(1, "10:05:00"),
                ),
                (
                    user_id,
                    product_ids["Бинт"],
                    "Бинт",
                    2,
                    "шт.",
                    "notification",
                    0,
                    _timestamp(1, "10:07:00"),
                ),
                (
                    user_id,
                    None,
                    "Пластыри",
                    1,
                    "упак.",
                    "manual",
                    0,
                    _timestamp(3, "19:20:00"),
                ),
                (
                    user_id,
                    None,
                    "Витамин C",
                    1,
                    "упак.",
                    "manual",
                    1,
                    _timestamp(6, "12:40:00"),
                ),
            ],
        )
        conn.executemany(
            "INSERT INTO history (user_id, product_id, action, description,"
            " created_at) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    user_id,
                    product_ids["Ибупрофен"],
                    "product_added",
                    "Ибупрофен · добавлен в аптечку",
                    _timestamp(6, "11:03:00"),
                ),
                (
                    user_id,
                    product_ids["Парацетамол"],
                    "product_updated",
                    "Парацетамол · количество изменено с 5 упак. до 10 упак.",
                    _timestamp(2, "18:32:00"),
                ),
                (
                    user_id,
                    product_ids["Бинт"],
                    "shopping_added",
                    "Бинт · добавлен в список покупок",
                    _timestamp(1, "10:07:00"),
                ),
            ],
        )
    return user_id


# --- полный набор: все состояния, действия истории и виды уведомлений ---

FULL_MARKER = "Аспирин Кардио"  # по этому товару видно, что набор уже загружен

# (название, категория, количество, единица, дней до конца срока или None,
#  место хранения, минимальный остаток, показания, примечание)
FULL_PRODUCTS = (
    # Просрочены.
    ("Аспирин Кардио", "Лекарства", 3, "упак.", -2, "Шкаф", 1, "Профилактика", ""),
    ("Цитрамон", "Лекарства", 12, "табл.", -120, "Шкаф", 4, "Головная боль", ""),
    ("Йод", "Медицинские товары", 1, "фл.", -400, "Аптечка", 1, "Антисептик", ""),
    ("Пантенол", "Лекарства", 50, "г", -10, "Холодильник", 20, "Ожоги", "Крем"),
    # Скоро истекает срок: сегодня, завтра, через 3, 7, 14, 29 дней.
    ("Нурофен сироп детский", "Лекарства", 100, "мл", 0, "Холодильник", 50, "", ""),
    (
        "Амоксициллин",
        "Лекарства",
        20,
        "табл.",
        1,
        "Шкаф",
        6,
        "Антибиотик",
        "По рецепту",
    ),
    ("Левомеколь", "Лекарства", 40, "г", 3, "Аптечка", 15, "Мазь для ран", ""),
    ("Супрастин", "Лекарства", 10, "табл.", 7, "Тумбочка", 4, "Аллергия", ""),
    ("Но-шпа", "Лекарства", 24, "табл.", 14, "Тумбочка", 6, "Спазмы", ""),
    ("Глицин", "Лекарства", 50, "табл.", 29, "Шкаф", 10, "", ""),
    # Низкий остаток (в том числе нулевой) и сразу два состояния.
    ("Перекись водорода", "Медицинские товары", 1, "фл.", 365, "Аптечка", 2, "", ""),
    ("Пластыри", "Медицинские товары", 0, "упак.", None, "Аптечка", 3, "", ""),
    ("Вата", "Медицинские товары", 5, "г", 700, "Аптечка", 50, "", ""),
    ("Зелёнка", "Медицинские товары", 1, "фл.", 500, "Аптечка", 1, "Антисептик", ""),
    ("Анальгин", "Лекарства", 1, "упак.", 5, "Шкаф", 2, "Обезболивающее", ""),
    # В норме: разные категории, единицы и места хранения.
    (
        "Термометр электронный",
        "Медицинские товары",
        2,
        "шт.",
        None,
        "Тумбочка",
        1,
        "",
        "",
    ),
    ("Шприцы 5 мл", "Медицинские товары", 20, "шт.", 800, "Аптечка", 5, "", ""),
    (
        "Маски медицинские",
        "Медицинские товары",
        50,
        "шт.",
        700,
        "Автомобиль",
        10,
        "",
        "",
    ),
    (
        "Перчатки нитриловые",
        "Медицинские товары",
        100,
        "шт.",
        None,
        "Аптечка",
        20,
        "",
        "",
    ),
    ("Мыло антибактериальное", "Средства гигиены", 3, "шт.", 900, "Ванная", 1, "", ""),
    ("Шампунь детский", "Средства гигиены", 450, "мл", 600, "Ванная", 100, "", ""),
    ("Зубная щётка", "Средства гигиены", 4, "шт.", None, "Ванная", 2, "", ""),
    ("Стиральный порошок", "Бытовая химия", 2500, "г", 365, "Кладовая", 500, "", ""),
    ("Средство для стёкол", "Бытовая химия", 1, "фл.", None, "Кладовая", 1, "", ""),
    (
        "Антисептик для рук",
        "Средства гигиены",
        250,
        "мл",
        40,
        "Рабочий стол",
        100,
        "",
        "",
    ),
    ("Магний B6 порошок", "Лекарства", 750, "мг", 90, "Кухня", 200, "", ""),
    ("Успокоительный сбор", "Лекарства", 1, "упак.", 60, "Кухня", 1, "Седативное", ""),
    (
        "Комплексный поливитаминный препарат с минералами для взрослых",
        "Лекарства",
        60,
        "табл.",
        200,
        "Кухня",
        20,
        "Витамины и минералы",
        "Принимать по одной таблетке в день после еды",
    ),
)

# (название, количество, единица, источник, куплено, товар аптечки или None,
#  дней назад, время). Источник: notification или manual.
FULL_SHOPPING = (
    ("Пластыри", 3, "упак.", "notification", 0, "Пластыри", 0, "09:15:00"),
    (
        "Перекись водорода",
        2,
        "фл.",
        "notification",
        0,
        "Перекись водорода",
        1,
        "18:40:00",
    ),
    ("Вата", 100, "г", "manual", 0, "Вата", 2, "12:00:00"),
    ("Бахилы", 10, "шт.", "manual", 0, None, 4, "20:10:00"),
    ("Тонометр", 1, "шт.", "manual", 0, None, 8, "08:30:00"),
    ("Спирт медицинский", 500, "мл", "manual", 0, None, 12, "15:25:00"),
    ("Йод", 1, "фл.", "notification", 1, "Йод", 5, "11:11:00"),
    ("Мыло жидкое", 2, "шт.", "manual", 1, None, 9, "17:45:00"),
    ("Бинт стерильный", 5, "шт.", "manual", 1, None, 15, "10:20:00"),
)

# Записи истории: (действие, товар или None, описание, дней назад, время).
FULL_HISTORY = (
    (
        "product_added",
        "Аспирин Кардио",
        "Аспирин Кардио · добавлен в аптечку",
        0,
        "09:02:00",
    ),
    (
        "product_updated",
        "Пантенол",
        "Пантенол · количество изменено с 80 г до 50 г",
        0,
        "09:20:00",
    ),
    (
        "shopping_added",
        "Пластыри",
        "Пластыри · 3 упак. · добавлено в список покупок",
        0,
        "09:15:00",
    ),
    ("product_added", "Левомеколь", "Левомеколь · добавлен в аптечку", 1, "13:30:00"),
    (
        "product_updated",
        "Но-шпа",
        "Но-шпа · изменено: срок годности, место хранения",
        1,
        "14:05:00",
    ),
    ("shopping_bought", None, "Йод · 1 фл. · куплено", 1, "19:00:00"),
    ("product_deleted", None, "Просроченный сироп · удалён из аптечки", 2, "10:10:00"),
    (
        "shopping_removed",
        None,
        "Бинт эластичный · 1 шт. · удалено из списка покупок",
        2,
        "16:45:00",
    ),
    (
        "product_added",
        "Зубная щётка",
        "Зубная щётка · добавлен в аптечку",
        3,
        "21:00:00",
    ),
    (
        "product_updated",
        "Супрастин",
        "Супрастин · минимальный остаток изменён с 2 табл. до 4 табл.",
        4,
        "08:15:00",
    ),
    (
        "shopping_added",
        "Вата",
        "Вата · 100 г · добавлено в список покупок",
        5,
        "12:00:00",
    ),
    ("shopping_bought", None, "Мыло жидкое · 2 шт. · куплено", 6, "17:50:00"),
    (
        "product_added",
        "Шампунь детский",
        "Шампунь детский · добавлен в аптечку",
        9,
        "11:11:00",
    ),
    ("product_deleted", None, "Аскорбинка · удалён из аптечки", 14, "09:40:00"),
    (
        "shopping_removed",
        None,
        "Градусник ртутный · 1 шт. · удалено из списка покупок",
        20,
        "14:20:00",
    ),
    (
        "product_updated",
        "Глицин",
        "Глицин · количество изменено с 100 табл. до 50 табл.",
        27,
        "18:30:00",
    ),
    ("shopping_bought", None, "Бинт стерильный · 5 шт. · куплено", 33, "10:25:00"),
    (
        "product_added",
        "Стиральный порошок",
        "Стиральный порошок · добавлен в аптечку",
        45,
        "16:00:00",
    ),
)

# Как «состарить» уведомления: сколько дней назад создано и прочитано ли.
# Порядок идёт по номеру уведомления, дальше список повторяется.
FULL_NOTIFICATION_AGES = (
    (0, False),
    (0, False),
    (1, False),
    (2, True),
    (3, False),
    (6, True),
    (10, False),
    (18, True),
    (28, False),
    (45, True),
)


def seed_full(db: Database, user_id: int) -> bool:
    """Дополняет демо-пользователя данными на все случаи интерфейса.

    Добавляются товары во всех состояниях (просрочен, скоро истекает, низкий
    остаток, сразу несколько состояний, норма, без срока, с длинным названием),
    список покупок (из уведомления, вручную, куплено, со ссылкой на товар),
    записи истории всех видов за разные дни и уведомления всех видов,
    прочитанные и нет, за разные периоды.

    Args:
        db: Менеджер базы данных с уже созданной схемой.
        user_id: Пользователь, которому добавляются данные.

    Returns:
        True, если данные добавлены, и False, если они уже были загружены.
    """
    from pharmacy.services.notification_service import NotificationService

    if db.fetch_one(
        "SELECT id FROM products WHERE user_id = ? AND name = ?",
        (user_id, FULL_MARKER),
    ):
        return False
    categories = {
        row["name"]: row["id"]
        for row in db.fetch_all("SELECT id, name FROM categories")
    }
    ids = {
        row["name"]: row["id"]
        for row in db.fetch_all(
            "SELECT id, name FROM products WHERE user_id = ?", (user_id,)
        )
    }
    with db.transaction() as conn:
        for (
            name,
            category,
            quantity,
            unit,
            days,
            place,
            minimum,
            notes,
            note,
        ) in FULL_PRODUCTS:
            ids[name] = conn.execute(
                "INSERT INTO products (user_id, category_id, name, quantity, unit,"
                " expiry_date, storage_place, min_quantity, indications, note)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    categories[category],
                    name,
                    quantity,
                    unit,
                    _expiry_from_today(days),
                    place,
                    minimum,
                    notes,
                    note,
                ),
            ).lastrowid
        conn.executemany(
            "INSERT INTO shopping_list (user_id, product_id, name, quantity, unit,"
            " source, is_bought, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    user_id,
                    ids.get(linked) if linked else None,
                    name,
                    quantity,
                    unit,
                    source,
                    bought,
                    _timestamp(ago, clock),
                )
                for name, quantity, unit, source, bought, linked, ago, clock in (
                    FULL_SHOPPING
                )
            ],
        )
        conn.executemany(
            "INSERT INTO history (user_id, product_id, action, description,"
            " created_at) VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, ids.get(product), action, text, _timestamp(ago, clock))
                for action, product, text, ago, clock in FULL_HISTORY
            ],
        )
    NotificationService(db).refresh(user_id)
    rows = db.fetch_all(
        "SELECT id FROM notifications WHERE user_id = ? ORDER BY id", (user_id,)
    )
    with db.transaction() as conn:
        for index, row in enumerate(rows):
            ago, read = FULL_NOTIFICATION_AGES[index % len(FULL_NOTIFICATION_AGES)]
            conn.execute(
                "UPDATE notifications SET is_read = ?, created_at = ? WHERE id = ?",
                (
                    int(read),
                    _timestamp(ago, f"{8 + index % 12:02d}:{index % 60:02d}:00"),
                    row["id"],
                ),
            )
    return True


def seed_bulk(db: Database, user_id: int, count: int = 1000, seed: int = 42) -> None:
    """Добавляет много товаров, чтобы проверить работу с большим объёмом данных.

    Args:
        db: Менеджер базы данных с уже созданной схемой.
        user_id: Пользователь, которому добавляются товары.
        count: Сколько товаров добавить.
        seed: Начальное значение генератора случайных чисел: при одинаковом
            значении получаются одинаковые данные.
    """
    rng = random.Random(seed)
    category_ids = [row["id"] for row in db.fetch_all("SELECT id FROM categories")]
    rows = []
    for number in range(1, count + 1):
        days = rng.choice([None] + list(range(-120, 720)))
        rows.append(
            (
                user_id,
                rng.choice(category_ids),
                f"Тестовый товар {number}",
                rng.randint(0, 20),
                "шт.",
                _expiry_from_today(days),
                rng.randint(0, 5),
            )
        )
    with db.transaction() as conn:
        conn.executemany(
            "INSERT INTO products (user_id, category_id, name, quantity, unit,"
            " expiry_date, min_quantity) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Точка входа консольной команды ``python -m pharmacy.db.seed``."""
    parser = argparse.ArgumentParser(description="Наполнение базы тестовыми данными")
    parser.add_argument("--bulk", type=int, default=0, help="добавить N товаров")
    parser.add_argument(
        "--full",
        action="store_true",
        help="добавить данные на все случаи: состояния, история, уведомления",
    )
    parser.add_argument(
        "--reset", action="store_true", help="удалить файл базы и создать заново"
    )
    args = parser.parse_args(argv)

    db = Database()
    if args.reset and db.path.exists():
        db.path.unlink()
        print(f"База {db.path} удалена")
    db.init_schema()

    user_id = seed_demo(db)
    if user_id is None:
        print("Демо-пользователь уже есть в базе")
        user_id = db.fetch_one("SELECT id FROM users WHERE login = ?", (DEMO_LOGIN,))[
            "id"
        ]
    else:
        print(f"Создан демо-пользователь {DEMO_LOGIN} (пароль: {DEMO_PASSWORD})")
    if args.full:
        if seed_full(db, user_id):
            print("Добавлен полный набор тестовых данных")
        else:
            print("Полный набор уже загружен")
    if args.bulk:
        seed_bulk(db, user_id, args.bulk)
        print(f"Добавлено товаров: {args.bulk}")
    print(f"База данных: {db.path}")


if __name__ == "__main__":
    main()
