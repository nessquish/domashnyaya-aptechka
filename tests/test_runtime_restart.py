"""Тест перезапуска программы: у собранного .exe распаковка должна идти заново."""

import os
import sys
import unittest
from unittest import mock

from tests import qt_helpers  # noqa: F401  (включает невидимую платформу Qt)
from pharmacy.ui import runtime


class RestartProgramTest(unittest.TestCase):
    def restart(self, frozen: bool):
        env = {}
        with mock.patch.dict(os.environ, {}, clear=False), mock.patch.object(
            runtime.QProcess, "startDetached"
        ) as start, mock.patch.object(runtime.QApplication, "quit"):
            os.environ.pop("PYINSTALLER_RESET_ENVIRONMENT", None)
            with mock.patch.object(sys, "frozen", frozen, create=True):
                runtime.restart_program()
            env["reset"] = os.environ.get("PYINSTALLER_RESET_ENVIRONMENT")
            env["args"] = start.call_args[0][1]
        return env

    def test_frozen_exe_unpacks_itself_again(self):
        env = self.restart(frozen=True)
        self.assertEqual(env["reset"], "1")
        self.assertEqual(env["args"], [])

    def test_source_run_restarts_module(self):
        env = self.restart(frozen=False)
        self.assertIsNone(env["reset"])
        self.assertEqual(env["args"], ["-m", "pharmacy"])


if __name__ == "__main__":
    unittest.main()
