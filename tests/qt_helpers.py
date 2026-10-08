"""Общие помощники для тестов интерфейса на Qt.

Тесты идут на невидимой платформе ``offscreen``: окна создаются и рисуются
в памяти, мигать на экране нечему.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest  # noqa: E402
from typing import List, Type  # noqa: E402

from PySide6.QtCore import QEvent, QPoint, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from pharmacy.db.seed import seed_demo  # noqa: E402
from pharmacy.services.container import build_services  # noqa: E402
from pharmacy.ui import paging, runtime, theme  # noqa: E402
from pharmacy.ui.app import App  # noqa: E402
from pharmacy.ui.screens.shell import MainShell  # noqa: E402
from pharmacy.ui.widgets.button import Button  # noqa: E402
from tests.helpers import DatabaseTestCase  # noqa: E402

runtime.application()


def settle(rounds: int = 4) -> None:
    """Даёт Qt выполнить отложенные действия: перерисовку и удаление виджетов."""
    for _ in range(rounds):
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def find_all(widget: QWidget, kind: Type) -> List:
    """Находит все видимые виджеты нужного класса внутри виджета."""
    found = [widget] if isinstance(widget, kind) and widget.isVisible() else []
    found.extend(w for w in widget.findChildren(kind) if w.isVisible())
    return found


def click(widget: QWidget, x: int = None, y: int = None) -> None:
    """Нажимает левой кнопкой мыши (по умолчанию в центр виджета)."""
    point = (
        QPoint(widget.width() // 2, widget.height() // 2) if x is None else QPoint(x, y)
    )
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, pos=point)


def type_text(widget: QWidget, text: str) -> None:
    """Печатает текст в виджет по символам (как с клавиатуры).

    ``QTest.keyClicks`` падает на кириллице, поэтому события клавиш
    собираются вручную: так вводит текст и сама система.
    """
    for char in text:
        for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            event = QKeyEvent(
                kind, Qt.Key.Key_unknown, Qt.KeyboardModifier.NoModifier, char
            )
            QApplication.sendEvent(widget, event)


class AppTestCase(DatabaseTestCase):
    """Приложение на временной базе с одним зарегистрированным пользователем."""

    def setUp(self) -> None:
        super().setUp()
        paging.AUTO_FIT = False  # страницы по 8 строк, окно теста не меряем
        self.addCleanup(setattr, paging, "AUTO_FIT", True)
        self.services = build_services(self.db)
        self.services.auth.register(
            "anna", "Анна", "anna@mail.ru", "password1", "password1"
        )
        self.app = App(self.services)
        self.addCleanup(self._close)
        self.app.show()
        self.settle()

    def _close(self) -> None:
        theme.set_theme(theme.LIGHT_THEME)
        theme.set_text_size(theme.DEFAULT_TEXT_SIZE)
        self.app.close()
        self.app.deleteLater()
        settle()

    def settle(self) -> None:
        settle()

    @property
    def screen(self) -> QWidget:
        return self.app.screen_widget

    def buttons(self, text: str) -> List[Button]:
        """Все видимые кнопки с такой подписью."""
        return [b for b in find_all(self.app, Button) if b.text() == text]


class ShellTestCase(AppTestCase):
    """Приложение с демо-данными, вход уже выполнен."""

    def setUp(self) -> None:
        super().setUp()
        seed_demo(self.db)
        self.screen._fields["login"].set("nessquish")
        self.screen._fields["password"].set("demo12345")
        self.screen._submit()
        self.settle()

    @property
    def shell(self) -> MainShell:
        return self.app.screen_widget

    @property
    def page(self) -> QWidget:
        """Экран открытого раздела."""
        return self.shell.current

    def open(self, name: str) -> QWidget:
        """Открывает раздел и возвращает его экран."""
        self.shell.navigate(name)
        self.settle()
        return self.shell.current


class WidgetTestCase(unittest.TestCase):
    """Отдельные виджеты в пустом окне (без приложения и базы)."""

    def setUp(self) -> None:
        self.root = QWidget()
        self.root.resize(600, 400)
        self.addCleanup(self._close)
        self.root.show()
        settle()

    def _close(self) -> None:
        theme.set_theme(theme.LIGHT_THEME)
        theme.set_text_size(theme.DEFAULT_TEXT_SIZE)
        self.root.close()
        self.root.deleteLater()
        settle()

    def settle(self) -> None:
        settle()
