"""Запоминание устройства на 30 дней."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from pharmacy.ui.remember import RememberedLogin


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
