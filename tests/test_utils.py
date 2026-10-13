"""Единицы, даты, форматирование, пароли и запоминание устройства."""

import unittest
from pharmacy.errors import ValidationError
from pharmacy.services.shopping_service import ShoppingService
from pharmacy.utils.units import DEFAULT_UNIT, UNITS, normalize_unit
from tests.helpers import DatabaseTestCase
from datetime import date
from pharmacy.utils.dates import days_until, format_user_date, parse_user_date
from pharmacy.utils.formatting import format_quantity, plural
from pharmacy.utils.security import hash_password, verify_password
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from pharmacy.ui.remember import RememberedLogin


class UnitListTest(unittest.TestCase):
    def test_default_unit_is_pieces_and_comes_first(self):
        self.assertEqual(DEFAULT_UNIT, "шт.")
        self.assertEqual(UNITS[0], DEFAULT_UNIT)

    def test_list_has_the_units_from_the_spec(self):
        for unit in ("шт.", "упак.", "табл.", "мг", "г", "мл"):
            self.assertIn(unit, UNITS)

    def test_units_are_unique(self):
        self.assertEqual(len(UNITS), len(set(UNITS)))


class NormalizeTest(unittest.TestCase):
    def test_listed_units_stay_as_they_are(self):
        for unit in UNITS:
            self.assertEqual(normalize_unit(unit), unit)

    def test_empty_unit_becomes_pieces(self):
        for empty in ("", " ", "\t"):
            self.assertEqual(normalize_unit(empty), "шт.")

    def test_case_and_spaces_do_not_matter(self):
        self.assertEqual(normalize_unit("  МЛ "), "мл")
        self.assertEqual(normalize_unit("Шт."), "шт.")

    def test_spelling_variants_are_united(self):
        for written in ("таб", "таб.", "табл", "Таблетки", "таблетка", "ТАБЛЕТОК"):
            self.assertEqual(normalize_unit(written), "табл.", written)
        for written in ("уп", "уп.", "упак", "упаковка"):
            self.assertEqual(normalize_unit(written), "упак.", written)
        for written in ("гр", "гр.", "грамм", "г."):
            self.assertEqual(normalize_unit(written), "г", written)

    def test_unknown_unit_is_rejected_with_the_field_name(self):
        with self.assertRaises(ValidationError) as ctx:
            normalize_unit("кубометр")
        self.assertEqual(ctx.exception.field, "unit")
        self.assertEqual(ctx.exception.message, "Выберите единицу измерения из списка")

    def test_custom_field_name(self):
        with self.assertRaises(ValidationError) as ctx:
            normalize_unit("???", field="u")
        self.assertEqual(ctx.exception.field, "u")


class ShoppingUnitTest(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.shopping = ShoppingService(self.db)
        self.user_id = self.add_user("anna")

    def test_manual_item_without_unit_gets_pieces(self):
        item = self.shopping.add_manual(self.user_id, "Вата", "2", "")
        self.assertEqual(item.unit, "шт.")

    def test_manual_item_spelling_is_united(self):
        item = self.shopping.add_manual(self.user_id, "Анальгин", "10", "таб")
        self.assertEqual(item.unit, "табл.")

    def test_manual_item_with_unknown_unit_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            self.shopping.add_manual(self.user_id, "Вата", "2", "тонн")
        self.assertEqual(ctx.exception.field, "unit")

    def test_history_of_shopping_shows_the_unit(self):
        from pharmacy.repositories.history_repository import HistoryRepository

        self.shopping.add_manual(self.user_id, "Парацетамол", "10", "мг")
        latest = HistoryRepository(self.db).list_for_user(self.user_id)[0]
        self.assertIn("10 мг", latest.description)


if __name__ == "__main__":
    unittest.main()


class DatesTest(unittest.TestCase):
    """Даты: ввод ДД.ММ.ГГГГ и расчёт дней."""

    def test_parse_user_date(self):
        self.assertEqual(parse_user_date("20.10.2026"), date(2026, 10, 20))

    def test_parse_ignores_spaces(self):
        self.assertEqual(parse_user_date("  01.02.2027 "), date(2027, 2, 1))

    def test_parse_rejects_wrong_formats(self):
        for text in ("", "2026-10-20", "20/10/2026", "32.01.2026", "29.02.2027", "abc"):
            with self.assertRaises(ValueError, msg=text):
                parse_user_date(text)

    def test_format_user_date(self):
        self.assertEqual(format_user_date(date(2026, 3, 5)), "05.03.2026")

    def test_format_empty_date(self):
        self.assertEqual(format_user_date(None), "")

    def test_days_until(self):
        today = date(2026, 10, 1)
        self.assertEqual(days_until(date(2026, 10, 20), today), 19)
        self.assertEqual(days_until(today, today), 0)
        self.assertEqual(days_until(date(2026, 9, 30), today), -1)


class FormattingTest(unittest.TestCase):
    """Красивая запись количества."""

    def test_integer_without_fraction(self):
        self.assertEqual(format_quantity(2.0), "2")
        self.assertEqual(format_quantity(10), "10")
        self.assertEqual(format_quantity(0), "0")

    def test_fraction_without_trailing_zeros(self):
        self.assertEqual(format_quantity(1.5), "1.5")
        self.assertEqual(format_quantity(0.25), "0.25")

    def test_large_number(self):
        self.assertEqual(format_quantity(1234567.5), "1234567.5")


class PluralTest(unittest.TestCase):
    """Склонение слов после чисел."""

    def forms(self, number):
        return plural(number, "день", "дня", "дней")

    def test_one(self):
        for number in (1, 21, 101):
            self.assertEqual(self.forms(number), "день", number)

    def test_few(self):
        for number in (2, 3, 4, 22, 24, 102):
            self.assertEqual(self.forms(number), "дня", number)

    def test_many(self):
        for number in (0, 5, 9, 10, 20, 25, 30, 100):
            self.assertEqual(self.forms(number), "дней", number)

    def test_teens_are_always_many(self):
        for number in (11, 12, 13, 14, 111, 112):
            self.assertEqual(self.forms(number), "дней", number)

    def test_negative_number_uses_absolute_value(self):
        self.assertEqual(self.forms(-1), "день")


if __name__ == "__main__":
    unittest.main()


class PasswordHashTest(unittest.TestCase):
    """Пароль не хранится в открытом виде и проверяется по хэшу."""

    def test_hash_does_not_contain_password(self):
        self.assertNotIn("secret123", hash_password("secret123"))

    def test_correct_password_accepted(self):
        stored = hash_password("secret123")
        self.assertTrue(verify_password("secret123", stored))

    def test_wrong_password_rejected(self):
        stored = hash_password("secret123")
        self.assertFalse(verify_password("secret124", stored))

    def test_same_password_gives_different_hashes(self):
        self.assertNotEqual(hash_password("secret123"), hash_password("secret123"))

    def test_malformed_hash_rejected(self):
        self.assertFalse(verify_password("secret123", "это-не-хэш"))
        self.assertFalse(verify_password("secret123", "md5$1$00$00"))
        self.assertFalse(verify_password("secret123", "pbkdf2_sha256$x$zz$zz"))

    def test_non_ascii_password(self):
        stored = hash_password("пароль-Ёж-123")
        self.assertTrue(verify_password("пароль-Ёж-123", stored))


if __name__ == "__main__":
    unittest.main()


class RememberedLoginTest(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.path = Path(self._dir.name) / "remember.json"

    def test_user_is_remembered_between_launches(self) -> None:
        RememberedLogin(self.path).remember(7, "hash")
        again = RememberedLogin(self.path)
        self.assertEqual(again.user_id(), 7)
        self.assertTrue(again.matches("hash"))

    def test_expires_after_thirty_days(self) -> None:
        start = datetime(2026, 1, 1)
        RememberedLogin(self.path).remember(7, "hash", now=start)
        again = RememberedLogin(self.path)
        self.assertEqual(again.user_id(start + timedelta(days=29)), 7)
        self.assertIsNone(again.user_id(start + timedelta(days=30)))
        self.assertFalse(self.path.exists())

    def test_password_change_invalidates(self) -> None:
        remembered = RememberedLogin(self.path)
        remembered.remember(7, "old")
        self.assertFalse(remembered.matches("new"))

    def test_clear_forgets(self) -> None:
        remembered = RememberedLogin(self.path)
        remembered.remember(7, "hash")
        remembered.clear()
        self.assertIsNone(RememberedLogin(self.path).user_id())

    def test_broken_file_is_ignored(self) -> None:
        self.path.write_text("{oops", encoding="utf-8")
        self.assertIsNone(RememberedLogin(self.path).user_id())


if __name__ == "__main__":
    unittest.main()
