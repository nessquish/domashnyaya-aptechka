"""Экран «Настройки»: слева список разделов, справа содержимое выбранного."""

import os
import sys
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QPoint, QProcess, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QApplication,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from pharmacy import GITHUB_URL, __build_date__, __developer__, __version__
from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.ui import paging, scaling, sections, theme
from pharmacy.ui.preferences import (
    GLOBAL_USER,
    MENU_ICONS,
    SCALE_MODE,
    SCALE_PERCENT,
)
from pharmacy.ui.theme import CARD_SHADOW_PAD, SHADOW_PAD
from pharmacy.ui.widgets.badge import Badge
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.common import Line, clear_layout, label, recolor
from pharmacy.ui.widgets.controls import Segmented, Slider, Toggle
from pharmacy.ui.widgets.dialog import Dialog, Modal
from pharmacy.ui.widgets.field import TextField
from pharmacy.ui.widgets.page import PageHeader
from pharmacy.ui.widgets.sidebar import NavItem

if TYPE_CHECKING:
    from pharmacy.ui.screens.shell import MainShell

APPEARANCE = "appearance"
NOTIFICATIONS = "notifications"
DATA = "data"
ACCOUNT = "account"
ABOUT = "about"
# Разделы сверху вниз: ключ, название, значок.
SECTIONS = (
    (APPEARANCE, "Внешний вид", "sliders"),
    (NOTIFICATIONS, "Уведомления", "bell"),
    (DATA, "Данные", "database"),
    (ACCOUNT, "Аккаунт", "user"),
    (ABOUT, "О программе", "info"),
)
HINT = "Выберите настройку"

MENU_WIDTH = 230
PAGE_MIN_HEIGHT = 320
SECTION_PADDING_X = 22
SECTION_PADDING_Y = 18
CARD_GAP = 16 - 2 * CARD_SHADOW_PAD
NOTICE_MS = 3000
SAVED = "Изменения сохранены"

THEMES = (
    (theme.LIGHT_THEME, "Светлая"),
    (theme.DARK_THEME, "Тёмная"),
    ("system", "Системная"),
)
MAX_DAYS = 30
DAYS_HINT = "Предупреждать заранее"
THRESHOLD_HINT = "0 — по минимальному остатку самого товара"
FIELD_WIDTH = 56
SCALE_MIN, SCALE_MAX = 80, 150
PROGRAM_NAME = "Моя аптечка"

EXPORT_FORMATS = (("csv", "CSV"), ("json", "JSON"), ("xlsx", "Excel"))
IMPORT_FORMATS = (("csv", "CSV"), ("json", "JSON"))
FILTERS = {
    "csv": "CSV (*.csv)",
    "json": "JSON (*.json)",
    "xlsx": "Excel (*.xlsx)",
}


class SettingsScreen(QWidget):
    """Список разделов слева, содержимое выбранного раздела справа."""

    def __init__(self, shell: "MainShell") -> None:
        super().__init__()
        self._shell = shell
        self._app = shell.app
        self._services = shell.services
        self._user = self._services.settings.get_user(shell.user.id)
        self._prefs = self._app.preferences
        self.section: Optional[str] = None
        self._items: Dict[str, NavItem] = {}
        self._fields: Dict[str, TextField] = {}
        self._notice: Optional[Badge] = None
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.setInterval(NOTICE_MS)
        self._notice_timer.timeout.connect(self._hide_notice)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._header = PageHeader("Настройки")
        layout.addWidget(self._header)
        layout.addSpacing(18 - CARD_SHADOW_PAD - SHADOW_PAD)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(CARD_GAP)
        top = Qt.AlignmentFlag.AlignTop
        body.addWidget(self._build_menu(), 0, top)
        body.addWidget(self._build_page_card(), 1, top)
        layout.addLayout(body)
        layout.addStretch(1)
        self._show_hint()
        reopen, self._app.reopen_settings = self._app.reopen_settings, None
        if reopen:
            self.open_section(reopen)
        notice = shell.take_notice()
        if notice:
            self._show_notice(notice)

    # --- каркас ---

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.fit_rows)

    def fit_rows(self) -> None:
        """Вытягивает фон обеих карточек до низа окна (текст остаётся на месте)."""
        height = self._shell.viewport_height()
        if height <= 0 or not self.isVisible():
            return
        top = self._menu_card.mapTo(self, QPoint(0, 0)).y()
        target = height - top - paging.BOTTOM_GAP
        for card in (self._menu_card, self._page_card):
            card.setMinimumHeight(max(target, 0))

    def _build_menu(self) -> Card:
        card = Card()
        self._menu_card = card
        card.setFixedWidth(MENU_WIDTH + 2 * card.inner_inset)
        host = QWidget()
        column = QVBoxLayout(host)
        column.setContentsMargins(
            10 - card.inner_inset,
            10 - card.inner_inset,
            10 - card.inner_inset,
            10 - card.inner_inset,
        )
        column.setSpacing(0)
        for key, title, icon in SECTIONS:
            item = NavItem(title, lambda k=key: self.open_section(k), icon=icon)
            column.addWidget(item)
            self._items[key] = item
        column.addStretch(1)
        card.body.addWidget(host)
        return card

    def _build_page_card(self) -> Card:
        self._page_card = Card()
        host = QWidget()
        self._page = QVBoxLayout(host)
        self._page.setContentsMargins(
            SECTION_PADDING_X - self._page_card.inner_inset,
            SECTION_PADDING_Y - self._page_card.inner_inset,
            SECTION_PADDING_X - self._page_card.inner_inset,
            SECTION_PADDING_Y - self._page_card.inner_inset,
        )
        self._page.setSpacing(0)
        host.setMinimumHeight(PAGE_MIN_HEIGHT)
        self._page_card.body.addWidget(host)
        return self._page_card

    def _show_hint(self) -> None:
        clear_layout(self._page)
        self._fields = {}
        text = label(HINT, "body", "ink_3")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint = text
        # Подсказка стоит там же, где и раньше, даже когда фон вытянут до низа.
        self._page.addSpacing(PAGE_MIN_HEIGHT // 2 - 24)
        self._page.addWidget(text)
        self._page.addStretch(1)
        for item in self._items.values():
            item.set_active(False)
        self.section = None

    def open_section(self, key: str) -> None:
        """Показывает справа содержимое раздела."""
        builders: Dict[str, Callable[[], None]] = {
            APPEARANCE: self._build_appearance,
            NOTIFICATIONS: self._build_notifications,
            DATA: self._build_data,
            ACCOUNT: self._build_account,
            ABOUT: self._build_about,
        }
        if key not in builders:
            raise ValueError(f"Неизвестный раздел настроек: {key}")
        clear_layout(self._page)
        self._fields = {}
        self.hint = None
        title = next(t for k, t, _ in SECTIONS if k == key)
        self._page.addWidget(label(title, "section"))
        self._page.addSpacing(14)
        for name, item in self._items.items():
            item.set_active(name == key)
        self.section = key
        builders[key]()
        self._page.addStretch(1)

    def _row(
        self, title: str, hint: str = "", first: bool = False
    ) -> Tuple[QHBoxLayout, Optional[QLabel]]:
        """Строка настройки: слева название и пояснение, справа элемент управления."""
        if not first:
            self._page.addWidget(Line("line_soft"))
        row = QHBoxLayout()
        row.setContentsMargins(0, 9, 0, 9)
        row.setSpacing(0)
        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(0)
        texts.addWidget(label(title, tight=True))
        note = None
        if hint:
            texts.addSpacing(2)
            note = label(hint, "caption", "ink_3", tight=True)
            texts.addWidget(note)
        row.addLayout(texts)
        row.addStretch(1)
        self._page.addLayout(row)
        return row, note

    @staticmethod
    def _caption(row: QHBoxLayout, text: str) -> None:
        row.addWidget(label(text, "body", "ink_2"))

    def _remember_section(self) -> None:
        """Запоминает раздел, чтобы после пересборки окна он открылся снова."""
        self._app.reopen_settings = self.section

    def _rebuild(self, notice: str = "") -> None:
        """Перестраивает окно (нужно после смены темы, размера текста, значков)."""
        self._remember_section()
        user = self._services.settings.get_user(self._user.id)
        self._app.apply_user_changes(user, notice, sections.SETTINGS)

    # --- внешний вид ---

    def _build_appearance(self) -> None:
        row, _ = self._row("Тема", "«Системная» повторяет тему Windows", first=True)
        mode = self._app.theme_mode(self._user)
        keys = [key for key, _name in THEMES]
        self._theme = Segmented(
            [name for _key, name in THEMES],
            keys.index(mode),
            self._on_theme,
            variant="outline",
        )
        row.addWidget(self._theme)

        scale_mode = self._prefs.get(GLOBAL_USER, SCALE_MODE, "auto")
        row, self._scale_hint = self._row("Масштаб", self._scale_text(scale_mode))
        self._scale_switch = Segmented(
            ["Авто", "Ручной"],
            1 if scale_mode == "manual" else 0,
            self._on_scale_mode,
            variant="outline",
        )
        row.addWidget(self._scale_switch)
        self._build_slider(scale_mode == "manual")

        row, _ = self._row("Размер шрифта")
        sizes = list(theme.TEXT_SIZES)
        self._text_size = Segmented(
            [theme.TEXT_SIZES[key][0] for key in sizes],
            sizes.index(theme.text_size_name()),
            self._on_text_size,
            variant="outline",
        )
        row.addWidget(self._text_size)

        row, _ = self._row("Значки в меню", "Рядом с названиями разделов слева")
        self._icons = Toggle(
            bool(self._prefs.get(self._user.id, MENU_ICONS, True)),
            self._on_menu_icons,
        )
        row.addWidget(self._icons)

        row, _ = self._row("Акцентный цвет", "Выбор из нескольких готовых цветов")
        row.addWidget(Badge("Скоро", "gray"))

    @staticmethod
    def _scale_text(mode: str) -> str:
        if mode == "manual":
            return "Задан вручную, применяется после перезапуска"
        return "Подбирается по разрешению и DPI экрана"

    def _build_slider(self, visible: bool) -> None:
        percent = int(
            self._prefs.get(
                GLOBAL_USER, SCALE_PERCENT, round(scaling.scale_factor() * 100)
            )
        )
        percent = max(SCALE_MIN, min(percent, SCALE_MAX))
        self._slider_row = QWidget()
        row = QHBoxLayout(self._slider_row)
        row.setContentsMargins(0, 0, 0, 8)
        row.addStretch(1)
        self._percent = label(f"{percent}%", "body_medium", "ink_2")
        row.addWidget(self._percent)
        row.addSpacing(14)
        self._slider = Slider(
            SCALE_MIN, SCALE_MAX, percent, self._on_slider, self._on_slider_done
        )
        row.addWidget(self._slider)
        self._slider_row.setVisible(visible)
        self._page.addWidget(self._slider_row)

    def _on_theme(self, index: int) -> None:
        self._remember_section()
        self._shell.set_theme(THEMES[index][0])

    def _on_scale_mode(self, index: int) -> None:
        mode = "manual" if index == 1 else "auto"
        self._prefs.set(GLOBAL_USER, SCALE_MODE, mode)
        if mode == "manual":
            self._prefs.set(GLOBAL_USER, SCALE_PERCENT, self._slider.value)
        self._slider_row.setVisible(mode == "manual")
        self._scale_hint.setText(self._scale_text(mode))
        if mode == "auto":
            self._ask_restart()

    def _on_slider(self, value: int) -> None:
        self._percent.setText(f"{value}%")

    def _on_slider_done(self, value: int) -> None:
        self._prefs.set(GLOBAL_USER, SCALE_PERCENT, value)
        if value != round(scaling.scale_factor() * 100):
            self._ask_restart()

    def _ask_restart(self) -> None:
        Dialog(
            self._app,
            "Применить масштаб?",
            "Масштаб меняется только при запуске. Перезапустить программу сейчас? "
            "Если устройство не запомнено, войти нужно будет заново.",
            "Перезапустить",
            self._restart,
            cancel_text="Позже",
            width=420,
        )

    def _restart(self) -> None:
        """Запускает программу заново (с новым масштабом) и закрывает эту."""
        # Масштаб текущего запуска не должен попасть в новый: он считается заново.
        os.environ.pop(scaling.ENV_NAME, None)
        args = [] if getattr(sys, "frozen", False) else ["-m", "pharmacy"]
        QProcess.startDetached(sys.executable, args)
        QApplication.quit()

    def _on_text_size(self, index: int) -> None:
        self._remember_section()
        self._shell.set_text_size(list(theme.TEXT_SIZES)[index])

    def _on_menu_icons(self, value: bool) -> None:
        self._prefs.set(self._user.id, MENU_ICONS, value)
        self._rebuild()

    # --- уведомления ---

    def _build_notifications(self) -> None:
        uid = self._user.id
        row, _ = self._row("Включить уведомления", "Общий выключатель", True)
        self._master = Toggle(
            bool(self._prefs.get(uid, "notify_enabled", True)), self._on_master
        )
        row.addWidget(self._master)

        row, _ = self._row("Срок годности истёк", "Напоминать о просроченных товарах")
        self._expired = Toggle(self._user.notify_expired, self._on_expired)
        row.addWidget(self._expired)

        row, self._days_hint = self._row("Скоро истекает срок", DAYS_HINT)
        self._expiring = Toggle(
            bool(self._prefs.get(uid, "notify_expiring", True)), self._on_expiring
        )
        self._caption(row, "за")
        self._days = TextField(
            width=FIELD_WIDTH, justify="center", on_change=self._days_edited
        )
        self._days.set(str(self._user.warning_days))
        row.addSpacing(4)
        row.addWidget(self._days)
        row.addSpacing(4)
        self._caption(row, "дн.")
        row.addSpacing(12)
        row.addWidget(self._expiring)

        row, self._low_hint = self._row("Низкий остаток", THRESHOLD_HINT)
        self._low = Toggle(self._user.notify_low_stock, self._on_low)
        self._caption(row, "меньше")
        self._threshold = TextField(
            width=FIELD_WIDTH, justify="center", on_change=self._threshold_edited
        )
        self._threshold.set(self._format_threshold())
        row.addSpacing(4)
        row.addWidget(self._threshold)
        row.addSpacing(4)
        self._caption(row, "шт.")
        row.addSpacing(12)
        row.addWidget(self._low)

    def _format_threshold(self) -> str:
        value = float(self._prefs.get(self._user.id, "low_threshold", 0) or 0)
        return str(int(value)) if value == int(value) else str(value)

    @property
    def master_toggle(self) -> Toggle:
        """Общий выключатель уведомлений."""
        return self._master

    @property
    def expired_toggle(self) -> Toggle:
        """Переключатель «Срок годности истёк»."""
        return self._expired

    @property
    def expiring_toggle(self) -> Toggle:
        """Переключатель «Скоро истекает срок»."""
        return self._expiring

    @property
    def low_toggle(self) -> Toggle:
        """Переключатель «Низкий остаток»."""
        return self._low

    @property
    def days_field(self) -> TextField:
        """Поле «за сколько дней предупреждать»."""
        return self._days

    @property
    def threshold_field(self) -> TextField:
        """Поле порога низкого остатка."""
        return self._threshold

    def _after_notify_change(self) -> None:
        self._services.notifications.refresh(self._user.id)
        self._shell.refresh_counters()
        self._show_notice(SAVED)

    def _save_flags(self, days: Optional[str] = None) -> None:
        self._user = self._services.settings.update_settings(
            self._user.id,
            days if days is not None else str(self._user.warning_days),
            theme.theme_name(),
            self._expired.value,
            self._low.value,
        )

    def _on_master(self, value: bool) -> None:
        self._prefs.set(self._user.id, "notify_enabled", value)
        self._after_notify_change()

    def _on_expired(self, _value: bool) -> None:
        self._save_flags()
        self._after_notify_change()

    def _on_low(self, _value: bool) -> None:
        self._save_flags()
        self._after_notify_change()

    def _on_expiring(self, value: bool) -> None:
        self._prefs.set(self._user.id, "notify_expiring", value)
        self._after_notify_change()

    def _days_edited(self) -> None:
        self._days.clear_error()
        self._set_hint(self._days_hint, DAYS_HINT, "ink_3")
        text = self._days.get().strip()
        if not text.isdigit() or not 1 <= int(text) <= MAX_DAYS:
            self._days.set_error()
            self._set_hint(self._days_hint, f"Число дней от 1 до {MAX_DAYS}", "red")
            return
        self._save_flags(text)
        self._after_notify_change()

    def _threshold_edited(self) -> None:
        self._threshold.clear_error()
        self._set_hint(self._low_hint, THRESHOLD_HINT, "ink_3")
        text = self._threshold.get().strip().replace(",", ".") or "0"
        try:
            value = float(text)
        except ValueError:
            value = -1
        if value < 0:
            self._threshold.set_error()
            self._set_hint(self._low_hint, "Введите число, не меньше нуля", "red")
            return
        self._prefs.set(self._user.id, "low_threshold", value)
        self._after_notify_change()

    @staticmethod
    def _set_hint(note: Optional[QLabel], text: str, color: str) -> None:
        if note is not None:
            note.setText(text)
            recolor(note, color)

    # --- данные ---

    def _build_data(self) -> None:
        row, _ = self._row("Экспорт данных", "Все товары аптечки в файл", first=True)
        for fmt, title in EXPORT_FORMATS:
            row.addWidget(Button(title, lambda f=fmt: self._export(f), size="sm"))
            row.addSpacing(4)
        row, _ = self._row("Импорт данных", "Добавить товары из файла")
        for fmt, title in IMPORT_FORMATS:
            row.addWidget(Button(title, self._import, size="sm"))
            row.addSpacing(4)
        row, _ = self._row("Очистить историю", "Удалить все записи истории")
        self.clear_history_button = Button(
            "Очистить", self._confirm_clear_history, variant="danger", size="sm"
        )
        row.addWidget(self.clear_history_button)
        row, _ = self._row(
            "Сбросить все данные", "Аптечка, список покупок, история и уведомления"
        )
        self.reset_button = Button(
            "Сбросить", self._confirm_reset, variant="danger", size="sm"
        )
        row.addWidget(self.reset_button)

    def _choose_save_path(self, fmt: str) -> str:
        path, _ = QFileDialog.getSaveFileName(
            self.window(), "Экспорт данных", f"aptechka.{fmt}", FILTERS[fmt]
        )
        return path

    def _choose_open_path(self) -> str:
        path, _ = QFileDialog.getOpenFileName(
            self.window(),
            "Импорт данных",
            "",
            "Файлы данных (*.csv *.json);;CSV (*.csv);;JSON (*.json)",
        )
        return path

    def _info(self, title: str, message: str) -> None:
        Dialog(
            self._app,
            title,
            message,
            "Понятно",
            lambda: None,
            info=True,
            width=420,
        )

    def _export(self, fmt: str) -> None:
        path = self._choose_save_path(fmt)
        if not path:
            return
        try:
            count = self._services.data.export_products(self._user.id, path, fmt)
        except (ValidationError, OSError) as error:
            self._info("Не удалось сохранить", str(getattr(error, "message", error)))
            return
        self._show_notice(f"Сохранено товаров: {count}")

    def _import(self) -> None:
        path = self._choose_open_path()
        if not path:
            return
        try:
            result = self._services.data.import_products(self._user.id, path)
        except ValidationError as error:
            self._info("Не удалось загрузить", error.message)
            return
        self._shell.refresh_counters()
        text = f"Добавлено товаров: {result.added}."
        if result.errors:
            text += f" Пропущено: {result.skipped}.\n" + "\n".join(result.errors[:5])
        self._info("Импорт завершён", text)

    def _confirm_clear_history(self) -> None:
        Dialog(
            self._app,
            "Очистить историю?",
            "Все записи истории будут удалены без возможности восстановления. "
            "Товары и список покупок не изменятся.",
            "Очистить",
            self._clear_history,
            confirm_variant="danger_solid",
            warning=True,
        )

    def _clear_history(self) -> None:
        self._services.history.clear(self._user.id)
        self._show_notice("История очищена")

    def _confirm_reset(self) -> None:
        Dialog(
            self._app,
            "Сбросить все данные?",
            "Будут удалены все товары, список покупок, история и уведомления. "
            "Аккаунт и настройки останутся. Это действие нельзя отменить.",
            "Сбросить",
            self._reset,
            confirm_variant="danger_solid",
            warning=True,
        )

    def _reset(self) -> None:
        self._services.data.reset_all(self._user.id)
        self._remember_section()
        self._shell.notice = "Все данные сброшены"
        self._shell.refresh()

    # --- аккаунт ---

    def _build_account(self) -> None:
        user = self._user
        row, _ = self._row("Имя пользователя", first=True)
        row.addWidget(label(user.username, "body", "ink_2"))
        row, _ = self._row("Логин")
        row.addWidget(label(user.login, "body", "ink_2"))
        row, _ = self._row("Электронная почта")
        row.addWidget(label(user.email, "body", "ink_2"))
        row.addSpacing(12)
        self.edit_email_button = Button("Изменить", self._edit_profile, size="sm")
        row.addWidget(self.edit_email_button)
        row, _ = self._row("Пароль", "Не менее 8 символов")
        self.password_button = Button("Сменить пароль", self._edit_password, size="sm")
        row.addWidget(self.password_button)
        row, _ = self._row("Выйти из аккаунта", "Понадобится ввести пароль снова")
        self.logout_button = Button("Выйти", self._shell.confirm_logout, size="sm")
        row.addWidget(self.logout_button)
        row, _ = self._row("Удалить аккаунт", "Вместе со всеми данными, навсегда")
        self.delete_button = Button(
            "Удалить", self._confirm_delete_account, variant="danger", size="sm"
        )
        row.addWidget(self.delete_button)

    def _edit_profile(self) -> None:
        self.profile_modal = ProfileModal(self._app, self._services, self._user, self)

    def _edit_password(self) -> None:
        self.password_modal = PasswordModal(self._app, self._services, self._user, self)

    def _confirm_delete_account(self) -> None:
        Dialog(
            self._app,
            "Удалить аккаунт?",
            "Аккаунт и все его данные будут удалены.",
            "Продолжить",
            self._confirm_delete_account_again,
            confirm_variant="danger_solid",
            warning=True,
        )

    def _confirm_delete_account_again(self) -> None:
        Dialog(
            self._app,
            "Точно удалить навсегда?",
            "Восстановить аккаунт и данные будет невозможно.",
            "Удалить навсегда",
            self._delete_account,
            confirm_variant="danger_solid",
            warning=True,
        )

    def _delete_account(self) -> None:
        try:
            self._services.auth.delete_account(self._user.id)
        except NotFoundError:
            pass
        self._app.sign_out()

    def saved(self, user, notice: str = SAVED) -> None:
        """Вызывают окна изменения профиля и пароля после сохранения."""
        self._user = user
        self._rebuild(notice)

    # --- о программе ---

    def _build_about(self) -> None:
        for index, (title, value) in enumerate(
            (
                ("Программа", PROGRAM_NAME),
                ("Версия", __version__),
                ("Дата сборки", __build_date__),
                ("Разработчик", __developer__),
            )
        ):
            row, _ = self._row(title, first=index == 0)
            row.addWidget(label(value, "body", "ink_2"))
        row, _ = self._row("Руководство", "Описание и исходный код на GitHub")
        self.guide_button = Button("Открыть", self._open_guide, size="sm")
        row.addWidget(self.guide_button)

    def _open_guide(self) -> None:
        QDesktopServices.openUrl(QUrl(GITHUB_URL))

    # --- уведомление «сохранено» ---

    def _show_notice(self, text: str) -> None:
        self._hide_notice()
        self._notice = Badge(text, "green", icon="check")
        self._header.actions.insertWidget(0, self._notice)
        self._notice_timer.start()

    def _hide_notice(self) -> None:
        if self._notice is not None:
            self._notice.setVisible(False)
            self._notice.deleteLater()
            self._notice = None

    @property
    def notice(self) -> Optional[Badge]:
        """Плашка «Изменения сохранены», пока она показана."""
        return self._notice

    @property
    def theme_switch(self) -> Segmented:
        """Выбор темы."""
        return self._theme

    @property
    def text_size_switch(self) -> Segmented:
        """Выбор размера текста."""
        return self._text_size

    @property
    def scale_switch(self) -> Segmented:
        """Выбор: автоматический или ручной масштаб."""
        return self._scale_switch

    @property
    def scale_slider(self) -> Slider:
        """Ползунок ручного масштаба."""
        return self._slider

    @property
    def icons_toggle(self) -> Toggle:
        """Переключатель значков в боковом меню."""
        return self._icons


class _FormModal(Modal):
    """Окно с полями и кнопками «Отмена» и «Сохранить»."""

    def __init__(
        self, app, title: str, fields: List[Tuple[str, str, bool]], save_text: str
    ) -> None:
        super().__init__(app, 400, on_enter=self._submit)
        self.add_title(title)
        self.fields: Dict[str, TextField] = {}
        for key, caption, password in fields:
            field = TextField(caption, password=password, required=True)
            field.bind_submit(self._submit)
            self.body.addWidget(field)
            self.body.addSpacing(2)
            self.fields[key] = field
        buttons = self.footer()
        self.cancel_button = Button("Отмена", self.close_modal)
        self.save_button = Button(save_text, self._submit, variant="primary")
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        next(iter(self.fields.values())).focus_field()

    def _show_error(self, error: ValidationError) -> None:
        for field in self.fields.values():
            field.clear_error()
        target = self.fields.get(error.field or "")
        if target is None:
            target = next(iter(self.fields.values()))
        target.set_error(error.message)
        target.focus_field()

    def _submit(self) -> None:
        raise NotImplementedError


class ProfileModal(_FormModal):
    """Изменение имени и электронной почты."""

    def __init__(self, app, services, user, screen: SettingsScreen) -> None:
        super().__init__(
            app,
            "Изменить данные",
            [("username", "Имя пользователя", False), ("email", "Эл. почта", False)],
            "Сохранить",
        )
        self._services = services
        self._user = user
        self._screen = screen
        self.fields["username"].set(user.username)
        self.fields["email"].set(user.email)

    def _submit(self) -> None:
        try:
            user = self._services.settings.update_profile(
                self._user.id,
                self.fields["username"].get(),
                self.fields["email"].get(),
            )
        except ValidationError as error:
            self._show_error(error)
            return
        self.close_modal()
        self._screen.saved(user)


class PasswordModal(_FormModal):
    """Смена пароля: текущий, новый и повтор нового."""

    def __init__(self, app, services, user, screen: SettingsScreen) -> None:
        super().__init__(
            app,
            "Сменить пароль",
            [
                ("old_password", "Текущий пароль", True),
                ("new_password", "Новый пароль", True),
                ("new_password_repeat", "Повторите новый пароль", True),
            ],
            "Сменить",
        )
        self._app = app
        self._services = services
        self._user = user
        self._screen = screen

    def _submit(self) -> None:
        new = self.fields["new_password"].get()
        try:
            self._services.auth.change_password(
                self._user.id,
                self.fields["old_password"].get(),
                new,
                self.fields["new_password_repeat"].get(),
            )
        except ValidationError as error:
            self._show_error(error)
            return
        self._app.session_password = new
        self._app.remembered.clear()
        self.close_modal()
        self._screen.saved(self._user, "Пароль изменён")
