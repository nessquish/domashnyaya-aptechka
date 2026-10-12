"""Выгрузка всех экранов программы для макета в Figma.

Запуск из папки проекта::

    .venv\\Scripts\\python.exe tools\\figma_export.py

Программа запускается на невидимой платформе с демо-данными, проходит по всем
экранам и окнам в светлой и в тёмной теме и для каждого сохраняет:

* ``design_export/<тема>/NN-название.svg`` — векторный кадр (в Figma остаётся
  редактируемым: текст, фигуры);
* ``design_export/<тема>/NN-название.png`` — то же в двойном размере;
* ``design_export/manifest.json`` — список кадров и переходов между ними
  (где нажимать и куда ведёт) для прототипа и схемы навигации.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt  # noqa: E402
from PySide6.QtGui import QImage, QKeyEvent, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgGenerator  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget  # noqa: E402

from pharmacy.db.connection import Database  # noqa: E402
from pharmacy.db.seed import seed_demo, seed_full  # noqa: E402
from pharmacy.services.container import build_services  # noqa: E402
from pharmacy.ui import paging, runtime, sections, theme  # noqa: E402
from pharmacy.ui.app import App  # noqa: E402
from pharmacy.ui.preferences import Preferences  # noqa: E402
from pharmacy.ui.screens.my_kit import MyKitScreen  # noqa: E402
from pharmacy.ui.screens.shopping import AddItemDialog  # noqa: E402
from pharmacy.ui.widgets.button import Button  # noqa: E402
from pharmacy.ui.widgets.dialog import Dialog, Modal  # noqa: E402
from pharmacy.utils import security  # noqa: E402

security._ITERATIONS = 1_000  # хэш пароля считается быстро: это только выгрузка

OUT = ROOT / "design_export"
SIZE = QSize(1280, 760)
THEMES = ("light", "dark")


def pause(ms: int = 80) -> None:
    """Даёт Qt выполнить отложенное (подгонку таблиц, удаление виджетов)."""
    QTest.qWait(ms)
    for _ in range(3):
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def type_text(widget: QWidget, text: str) -> None:
    for char in text:
        for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QApplication.sendEvent(
                widget,
                QKeyEvent(
                    kind, Qt.Key.Key_unknown, Qt.KeyboardModifier.NoModifier, char
                ),
            )


def find_label(root: QWidget, text: str) -> Optional[QLabel]:
    for widget in root.findChildren(QLabel):
        if widget.isVisible() and widget.text() == text:
            return widget
    return None


def find_button(root: QWidget, text: str) -> Optional[Button]:
    for widget in root.findChildren(Button):
        if widget.isVisible() and widget.text() == text:
            return widget
    return None


def modal_of(app: App, kind: type = Modal) -> Optional[Modal]:
    for widget in app.findChildren(kind):
        if widget.isVisible() and getattr(widget, "is_open", False):
            return widget
    return None


class Exporter:
    """Один проход по всем экранам в одной теме."""

    def __init__(self, theme_name: str) -> None:
        self.theme = theme_name
        self.folder = OUT / theme_name
        shutil.rmtree(self.folder, ignore_errors=True)
        self.folder.mkdir(parents=True)
        self.tmp = tempfile.TemporaryDirectory()
        runtime.system_theme = lambda: theme_name
        db = Database(Path(self.tmp.name) / "export.db")
        db.init_schema()
        user_id = seed_demo(db)
        seed_full(db, user_id)
        self.services = build_services(db)
        self.app = App(self.services, Preferences(Path(self.tmp.name) / "prefs.json"))
        self.app.resize(SIZE)
        self.app.show()
        paging.AUTO_FIT = True
        pause(200)
        self.frames: List[dict] = []
        self.links: List[dict] = []

    # --- помощники ---

    @property
    def shell(self):
        return self.app.screen_widget

    @property
    def page(self):
        return self.shell.current

    def rect(self, widget: QWidget) -> List[int]:
        point = widget.mapTo(self.app, QPoint(0, 0))
        return [point.x(), point.y(), widget.width(), widget.height()]

    def close_modals(self) -> None:
        for _ in range(4):
            modal = modal_of(self.app)
            if modal is None:
                break
            modal.close_modal()
            pause()

    def sign_in(self, login: str = "nessquish", password: str = "demo12345") -> None:
        user = self.services.auth.login(login, password)
        self.app.sign_in(user, password)
        pause(150)

    def go(self, section: str) -> None:
        self.close_modals()
        self.shell.navigate(section)
        pause(250)

    def product_id(self, name: str) -> int:
        views = self.services.products.list_products(self.app.user.id)
        return next(v.product.id for v in views if v.product.name == name)

    # --- кадры ---

    def capture(self, number: int, title: str, links: Optional[List[dict]] = None):
        """Сохраняет текущий вид окна как кадр ``number`` и его переходы."""
        pause(120)
        slug = f"{number:02d}"
        name = f"{slug} {title}"
        svg = self.folder / f"{slug}.svg"
        png = self.folder / f"{slug}.png"
        generator = QSvgGenerator()
        generator.setFileName(str(svg))
        generator.setSize(SIZE)
        generator.setViewBox(QRect(0, 0, SIZE.width(), SIZE.height()))
        generator.setTitle(name)
        generator.setResolution(96)
        painter = QPainter(generator)
        self.app.render(painter, QPoint(0, 0))
        painter.end()
        image = QImage(SIZE * 2, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        painter.scale(2, 2)
        self.app.render(painter, QPoint(0, 0))
        painter.end()
        image.save(str(png))
        self.frames.append(
            {
                "id": slug,
                "number": number,
                "title": title,
                "name": name,
                "theme": self.theme,
                "svg": f"{self.theme}/{slug}.svg",
                "png": f"{self.theme}/{png.name}",
                "width": SIZE.width(),
                "height": SIZE.height(),
            }
        )
        for link in links or []:
            if link.get("widget") is None:
                continue
            self.links.append(
                {
                    "from": slug,
                    "to": f"{link['to']:02d}",
                    "label": link["label"],
                    "rect": self.rect(link["widget"]),
                    "overlay": bool(link.get("overlay")),
                }
            )

    def nav_links(self) -> List[dict]:
        """Переходы бокового меню (одинаковые на всех экранах после входа)."""
        sidebar = self.shell.sidebar
        pairs = [
            (sections.HOME, 3),
            (sections.MY_KIT, 4),
            (sections.SHOPPING, 9),
            (sections.NOTIFICATIONS, 11),
            (sections.HISTORY, 12),
            (sections.SETTINGS, 13),
        ]
        links = [
            {"label": f"Меню: {name}", "widget": sidebar.item(name), "to": target}
            for name, target in pairs
        ]
        links.append(
            {
                "label": "Меню: Поиск",
                "widget": sidebar.search_button,
                "to": 24,
                "overlay": True,
            }
        )
        links.append({"label": "Профиль", "widget": sidebar.profile, "to": 20})
        links.append(
            {
                "label": "Выход",
                "widget": sidebar.logout_link,
                "to": 14,
                "overlay": True,
            }
        )
        return links

    def settings_links(self, own: int) -> List[dict]:
        keys = {
            17: "appearance",
            18: "notifications",
            19: "data",
            20: "account",
            21: "about",
        }
        links = []
        for number, key in keys.items():
            if number != own and self.page.section is not None:
                links.append(
                    {
                        "label": f"Настройки: {self.page._items[key].text()}",
                        "widget": self.page._items[key],
                        "to": number,
                    }
                )
        return links

    # --- весь проход ---

    def run(self) -> None:
        screen = self.app.screen_widget
        self.capture(
            1,
            "Авторизация",
            [
                {"label": "Зарегистрироваться", "widget": screen.switch_link, "to": 2},
                {"label": "Войти", "widget": screen.submit_button, "to": 3},
            ],
        )
        self.app.show_register()
        pause(200)
        screen = self.app.screen_widget
        self.capture(
            2,
            "Регистрация",
            [
                {"label": "Войти", "widget": screen.switch_link, "to": 1},
                {
                    "label": "Зарегистрироваться",
                    "widget": screen.submit_button,
                    "to": 3,
                },
            ],
        )
        self.app.show_login()
        pause(100)
        self.sign_in()

        # 03 Главная
        self.go(sections.HOME)
        attention = self.page.attention_card
        first_product = next(
            (
                w
                for w in attention.findChildren(QWidget)
                if hasattr(w, "text") and callable(w.text) and w.text() == "Йод"
            ),
            None,
        )
        self.capture(
            3,
            "Главная",
            self.nav_links()
            + [
                {
                    "label": "Добавить товар",
                    "widget": self.page.findChild(Button),
                    "to": 5,
                    "overlay": True,
                },
                {
                    "label": "Товар: карточка",
                    "widget": first_product,
                    "to": 6,
                    "overlay": True,
                },
            ],
        )

        # 04 Моя аптечка
        self.go(sections.MY_KIT)
        kit: MyKitScreen = self.page
        name_label = kit.table.cell_widgets(0)[0]
        box = kit.table.check_widgets()[0]
        self.capture(
            4,
            "Моя аптечка",
            self.nav_links()
            + [
                {
                    "label": "Добавить товар",
                    "widget": kit.add_button,
                    "to": 5,
                    "overlay": True,
                },
                {
                    "label": "Название товара",
                    "widget": name_label,
                    "to": 6,
                    "overlay": True,
                },
                {"label": "Выбрать товар", "widget": box, "to": 16},
            ],
        )

        # 05 Добавить товар
        self.shell.add_product()
        pause(250)
        form = modal_of(self.app)
        self.capture(
            5,
            "Добавить товар",
            [
                {"label": "Отмена", "widget": form.cancel_button, "to": 4},
                {"label": "Сохранить", "widget": form.save_button, "to": 4},
            ],
        )
        self.close_modals()

        # 06 Карточка товара
        self.shell.open_product(self.product_id("Ибупрофен"))
        pause(250)
        card = modal_of(self.app)
        self.capture(
            6,
            "Карточка товара",
            [
                {
                    "label": "Редактировать",
                    "widget": card.edit_button,
                    "to": 7,
                    "overlay": True,
                },
                {
                    "label": "Удалить",
                    "widget": card.delete_button,
                    "to": 8,
                    "overlay": True,
                },
                {"label": "В список покупок", "widget": card.list_button, "to": 9},
                {"label": "Закрыть", "widget": card.close_button, "to": 4},
            ],
        )
        card_id = self.product_id("Ибупрофен")

        # 08 Подтверждение удаления (из карточки)
        card.delete_button.invoke()
        pause(250)
        dialog = modal_of(self.app, Dialog)
        self.capture(
            8,
            "Подтверждение удаления",
            [
                {"label": "Отмена", "widget": dialog.cancel_button, "to": 6},
                {"label": "Удалить", "widget": dialog.confirm_button, "to": 4},
            ],
        )
        self.close_modals()

        # 07 Редактирование товара
        self.shell.edit_product(card_id)
        pause(250)
        edit = modal_of(self.app)
        self.capture(
            7,
            "Редактирование товара",
            [
                {"label": "Отмена", "widget": edit.cancel_button, "to": 6},
                {"label": "Сохранить изменения", "widget": edit.save_button, "to": 6},
            ],
        )
        self.close_modals()

        # 09 Список покупок
        self.go(sections.SHOPPING)
        shop = self.page
        self.capture(
            9,
            "Список покупок",
            self.nav_links()
            + [
                {
                    "label": "Добавить вручную",
                    "widget": shop.add_button,
                    "to": 10,
                    "overlay": True,
                },
                {
                    "label": "Выбрать позицию",
                    "widget": (
                        shop.boxes()[0]
                        if hasattr(shop, "boxes")
                        else shop.table.cell_widgets(0)[0]
                    ),
                    "to": 26,
                },
            ],
        )

        # 10 Добавить в список вручную (с подсказками)
        shop.add_button.invoke()
        pause(250)
        add = modal_of(self.app, AddItemDialog)
        add.name.entry.setFocus()
        type_text(add.name.entry, "вит")
        pause(150)
        self.capture(
            10,
            "Добавить в список вручную",
            [
                {"label": "Отмена", "widget": add.cancel_button, "to": 9},
                {"label": "Добавить", "widget": add.add_button, "to": 9},
            ],
        )
        self.close_modals()

        # 11 Уведомления
        self.go(sections.NOTIFICATIONS)
        self.capture(
            11,
            "Уведомления",
            self.nav_links()
            + [
                {
                    "label": "Открыть товар",
                    "widget": find_button(self.page, "Открыть товар"),
                    "to": 6,
                    "overlay": True,
                },
                {
                    "label": "В список покупок",
                    "widget": find_button(self.page, "В список покупок"),
                    "to": 9,
                },
            ],
        )

        # 12 История
        self.go(sections.HISTORY)
        self.capture(
            12,
            "История",
            self.nav_links()
            + [
                {
                    "label": "Очистить историю",
                    "widget": self.page.clear_button,
                    "to": 27,
                    "overlay": True,
                }
            ],
        )

        # 27 Очистка истории
        self.page.clear_button.invoke()
        pause(250)
        dialog = modal_of(self.app, Dialog)
        self.capture(
            27,
            "Очистка истории",
            [
                {"label": "Отмена", "widget": dialog.cancel_button, "to": 12},
                {"label": "Очистить", "widget": dialog.confirm_button, "to": 12},
            ],
        )
        self.close_modals()

        # 13 Настройки (ничего не выбрано)
        self.go(sections.SETTINGS)
        settings = self.page
        links = self.nav_links()
        for number, key in {
            17: "appearance",
            18: "notifications",
            19: "data",
            20: "account",
            21: "about",
        }.items():
            links.append(
                {
                    "label": f"Настройки: {settings._items[key].text()}",
                    "widget": settings._items[key],
                    "to": number,
                }
            )
        self.capture(13, "Настройки", links)

        # 17–21 разделы настроек
        for number, key, title in (
            (17, "appearance", "Настройки — Внешний вид"),
            (18, "notifications", "Настройки — Уведомления"),
            (19, "data", "Настройки — Данные"),
            (20, "account", "Настройки — Аккаунт"),
            (21, "about", "Настройки — О программе"),
        ):
            settings.open_section(key)
            pause(250)
            links = self.nav_links() + self.settings_links(number)
            if key == "data":
                links += [
                    {
                        "label": "Очистить историю",
                        "widget": settings.clear_history_button,
                        "to": 27,
                        "overlay": True,
                    },
                    {
                        "label": "Сбросить все данные",
                        "widget": settings.reset_button,
                        "to": 30,
                        "overlay": True,
                    },
                ]
            if key == "account":
                links += [
                    {
                        "label": "Изменить логин",
                        "widget": settings.edit_login_button,
                        "to": 23,
                        "overlay": True,
                    },
                    {
                        "label": "Сменить пароль",
                        "widget": settings.password_button,
                        "to": 22,
                        "overlay": True,
                    },
                    {
                        "label": "Выйти",
                        "widget": settings.logout_button,
                        "to": 14,
                        "overlay": True,
                    },
                    {
                        "label": "Удалить аккаунт",
                        "widget": settings.delete_button,
                        "to": 29,
                        "overlay": True,
                    },
                ]
            self.capture(number, title, links)

        # 22 Смена пароля, 23 Изменение логина
        settings.open_section("account")
        pause(200)
        settings.password_button.invoke()
        pause(250)
        modal = modal_of(self.app)
        self.capture(
            22,
            "Смена пароля",
            [
                {"label": "Отмена", "widget": modal.cancel_button, "to": 20},
                {"label": "Сменить", "widget": modal.save_button, "to": 20},
            ],
        )
        self.close_modals()
        settings.edit_login_button.invoke()
        pause(250)
        modal = modal_of(self.app)
        self.capture(
            23,
            "Изменение логина",
            [
                {"label": "Отмена", "widget": modal.cancel_button, "to": 20},
                {"label": "Сохранить", "widget": modal.save_button, "to": 20},
            ],
        )
        self.close_modals()

        # 29, 31 Удаление аккаунта (двойное подтверждение)
        settings.delete_button.invoke()
        pause(250)
        first = modal_of(self.app, Dialog)
        self.capture(
            29,
            "Удаление аккаунта",
            [
                {"label": "Отмена", "widget": first.cancel_button, "to": 20},
                {
                    "label": "Продолжить",
                    "widget": first.confirm_button,
                    "to": 31,
                    "overlay": True,
                },
            ],
        )
        self.close_modals()
        settings._confirm_delete_account_again()
        pause(250)
        second = modal_of(self.app, Dialog)
        self.capture(
            31,
            "Удаление аккаунта — подтверждение",
            [
                {"label": "Отмена", "widget": second.cancel_button, "to": 20},
                {"label": "Удалить навсегда", "widget": second.confirm_button, "to": 1},
            ],
        )
        self.close_modals()

        # 30 Сброс всех данных
        settings.open_section("data")
        pause(200)
        settings.reset_button.invoke()
        pause(250)
        dialog = modal_of(self.app, Dialog)
        self.capture(
            30,
            "Сброс всех данных",
            [
                {"label": "Отмена", "widget": dialog.cancel_button, "to": 19},
                {"label": "Сбросить", "widget": dialog.confirm_button, "to": 15},
            ],
        )
        self.close_modals()

        # 32 Применить масштаб
        settings.open_section("appearance")
        pause(200)
        settings._ask_restart()
        pause(250)
        dialog = modal_of(self.app, Dialog)
        self.capture(
            32,
            "Применить масштаб",
            [
                {"label": "Позже", "widget": dialog.cancel_button, "to": 17},
                {"label": "Перезапустить", "widget": dialog.confirm_button, "to": 1},
            ],
        )
        self.close_modals()

        # 14 Подтверждение выхода
        self.go(sections.HOME)
        self.shell.confirm_logout()
        pause(250)
        dialog = modal_of(self.app, Dialog)
        self.capture(
            14,
            "Подтверждение выхода",
            [
                {"label": "Отмена", "widget": dialog.cancel_button, "to": 3},
                {"label": "Выйти", "widget": dialog.confirm_button, "to": 1},
            ],
        )
        self.close_modals()

        # 16 Моя аптечка — выбор товаров, 28 удаление выбранных
        self.go(sections.MY_KIT)
        kit = self.page
        for box in kit.table.check_widgets()[:2]:
            box.set(True)
        kit._toggle(kit._shown_ids[0], True)
        kit._toggle(kit._shown_ids[1], True)
        pause(250)
        self.capture(
            16,
            "Моя аптечка — выбор товаров",
            self.nav_links()
            + [
                {"label": "В список покупок", "widget": kit.shopping_button, "to": 9},
                {
                    "label": "Удалить выбранные",
                    "widget": kit.delete_button,
                    "to": 28,
                    "overlay": True,
                },
                {"label": "Снять выбор", "widget": kit.clear_button, "to": 4},
            ],
        )
        kit.delete_button.invoke()
        pause(250)
        dialog = modal_of(self.app, Dialog)
        self.capture(
            28,
            "Удаление выбранных товаров",
            [
                {"label": "Отмена", "widget": dialog.cancel_button, "to": 16},
                {"label": "Удалить", "widget": dialog.confirm_button, "to": 4},
            ],
        )
        self.close_modals()

        # 26 Список покупок — выбор позиций
        self.go(sections.SHOPPING)
        shop = self.page
        for item in shop._visible[:2]:
            shop._toggle(item.id, True)
        pause(250)
        self.capture(
            26,
            "Список покупок — выбор позиций",
            self.nav_links()
            + [{"label": "Снять выбор", "widget": shop.clear_button, "to": 9}],
        )

        # 24, 25 Поиск
        self.go(sections.HOME)
        self.app.open_search()
        pause(250)
        search = self.app.search_modal
        self.capture(
            24,
            "Поиск",
            [{"label": "Закрыть", "widget": search.close_button, "to": 3}],
        )
        search.field.set("ибупрофен")
        search._update()
        pause(300)
        targets = {
            "product": 4,
            "card": 6,
            "shopping": 9,
            "notification": 11,
            "history": 12,
        }
        links = [{"label": "Закрыть", "widget": search.close_button, "to": 3}]
        seen = set()
        for row in search.rows:
            kind = row.target.kind
            if kind in targets and kind not in seen:
                seen.add(kind)
                links.append(
                    {
                        "label": f"Результат: {kind}",
                        "widget": row,
                        "to": targets[kind],
                        "overlay": kind == "card",
                    }
                )
        self.capture(25, "Поиск — результаты", links)
        self.close_modals()

        # 15 Пустая аптечка
        self.app.sign_out()
        pause(150)
        self.services.auth.register(
            "empty", "Новый", "empty@mail.ru", "password1", "password1"
        )
        self.sign_in("empty", "password1")
        self.go(sections.MY_KIT)
        self.capture(
            15,
            "Пустая аптечка",
            self.nav_links()
            + [
                {
                    "label": "Добавить первый товар",
                    "widget": find_button(self.page, "Добавить товар в аптечку"),
                    "to": 5,
                    "overlay": True,
                }
            ],
        )

    def finish(self) -> dict:
        self.frames.sort(key=lambda frame: frame["number"])
        self.app.close()
        return {"frames": self.frames, "links": self.links}


def main() -> None:
    runtime.application()
    OUT.mkdir(exist_ok=True)
    manifest: Dict[str, dict] = {}
    for name in THEMES:
        exporter = Exporter(name)
        exporter.run()
        manifest[name] = exporter.finish()
        print(
            f"{name}: кадров {len(manifest[name]['frames'])}, "
            f"переходов {len(manifest[name]['links'])}"
        )
        theme.set_theme(theme.LIGHT_THEME)
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
