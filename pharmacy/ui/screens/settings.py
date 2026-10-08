"""Экран «Настройки» (макет Figma, экран 13): профиль, пароль, уведомления, тема."""

from typing import TYPE_CHECKING, Dict, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.ui.widgets.badge import Badge
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.common import Line, label, recolor
from pharmacy.ui.widgets.controls import Segmented, Toggle
from pharmacy.ui.widgets.field import TextField
from pharmacy.ui.widgets.page import PageHeader
from pharmacy.ui import sections, theme
from pharmacy.ui.theme import CARD_SHADOW_PAD, SHADOW_PAD

if TYPE_CHECKING:
    from pharmacy.ui.screens.shell import MainShell

SECTION_PADDING_X = 20
SECTION_PADDING_Y = 18
CARD_GAP = 16 - 2 * CARD_SHADOW_PAD
FIELD_GAP = 2  # 10 px по макету минус поля под тень у соседних полей
THEMES = ((theme.LIGHT_THEME, "Светлая"), (theme.DARK_THEME, "Тёмная"))
DAYS_FIELD_WIDTH = 56
NOTICE_MS = 3000
SAVED = "Изменения сохранены"
DAYS_HINT = "Предупреждать заранее"


class SettingsScreen(QWidget):
    """Четыре карточки настроек и сохранение одной кнопкой."""

    def __init__(self, shell: "MainShell") -> None:
        super().__init__()
        self._shell = shell
        self._services = shell.services
        self._user = self._services.settings.get_user(shell.user.id)
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
        self.cancel_button = Button("Отмена", command=self._cancel)
        self.save_button = Button(
            "Сохранить изменения", command=self._save, variant="primary"
        )
        self._header.actions.addWidget(self.cancel_button)
        self._header.actions.addWidget(self.save_button)
        layout.addWidget(self._header)
        layout.addSpacing(18 - CARD_SHADOW_PAD - SHADOW_PAD)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(CARD_GAP)
        grid.setVerticalSpacing(CARD_GAP)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        top = Qt.AlignmentFlag.AlignTop
        grid.addWidget(self._build_profile(), 0, 0, top)
        grid.addWidget(self._build_password(), 0, 1, top)
        grid.addWidget(self._build_notifications(), 1, 0, top)
        grid.addWidget(self._build_appearance(), 1, 1, top)
        layout.addLayout(grid)
        layout.addStretch(1)
        notice = shell.take_notice()
        if notice:
            self._show_notice(notice)

    @property
    def fields(self) -> Dict[str, TextField]:
        """Текстовые поля по ключам (``username``, ``email``, ``new_password`` ...)."""
        return self._fields

    @property
    def notice(self) -> Optional[Badge]:
        """Плашка «Изменения сохранены», пока она показана."""
        return self._notice

    # --- общие части карточек ---

    def _section(self, title: str, hint: str) -> Tuple[Card, QVBoxLayout]:
        """Карточка с заголовком и пояснением. Возвращает её и раскладку содержимого."""
        card = Card()
        host = QWidget()
        inner = QVBoxLayout(host)
        inner.setContentsMargins(
            SECTION_PADDING_X - card.inner_inset,
            SECTION_PADDING_Y - card.inner_inset,
            SECTION_PADDING_X - card.inner_inset,
            SECTION_PADDING_Y - card.inner_inset,
        )
        inner.setSpacing(0)
        inner.addWidget(label(title, "section"))
        inner.addSpacing(4)
        inner.addWidget(label(hint, "small", "ink_3"))
        inner.addSpacing(14)
        card.body.addWidget(host)
        return card, inner

    def _field(self, inner: QVBoxLayout, key: str, title: str, **options) -> TextField:
        field = TextField(title, **options)
        inner.addWidget(field)
        inner.addSpacing(FIELD_GAP)
        self._fields[key] = field
        return field

    def _row(
        self, inner: QVBoxLayout, title: str, hint: str = "", first: bool = False
    ) -> Tuple[QHBoxLayout, Optional[QLabel]]:
        """Строка настройки: слева название и пояснение, справа элемент управления.

        Returns:
            Раскладка строки (в неё кладётся элемент управления) и подпись-пояснение.
        """
        if not first:
            inner.addWidget(Line("line_soft"))
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
        inner.addLayout(row)
        return row, note

    @staticmethod
    def _caption(row: QHBoxLayout, text: str) -> None:
        """Слово рядом с полем числа («за» и «дней»)."""
        row.addWidget(label(text, "body", "ink_2"))

    # --- карточки ---

    def _build_profile(self) -> Card:
        card, inner = self._section("Профиль", "Данные вашей учётной записи")
        self._field(inner, "username", "Имя пользователя").set(self._user.username)
        self._field(inner, "login", "Логин", readonly=True).set(self._user.login)
        self._field(inner, "email", "Электронная почта").set(self._user.email)
        return card

    def _build_password(self) -> Card:
        card, inner = self._section("Смена пароля", "Не менее 8 символов")
        # Текущий пароль только показывается (значок «глаз»), изменить его здесь
        # нельзя. Он известен лишь из входа в этом сеансе: в базе только хэш.
        current = self._field(
            inner,
            "old_password",
            "Текущий пароль",
            placeholder="••••••••",
            password=True,
            readonly=bool(self._shell.app.session_password),
        )
        current.set(self._shell.app.session_password)
        self._field(
            inner,
            "new_password",
            "Новый пароль",
            placeholder="Введите новый пароль",
            password=True,
        )
        self._field(
            inner,
            "new_password_repeat",
            "Повторите новый пароль",
            placeholder="Повторите пароль",
            password=True,
        )
        return card

    def _build_notifications(self) -> Card:
        card, inner = self._section(
            "Уведомления", "Когда приложение должно предупреждать"
        )
        row, _ = self._row(inner, "Срок годности истёк", first=True)
        self._expired = Toggle(self._user.notify_expired)
        row.addWidget(self._expired)

        row, self._days_hint = self._row(inner, "Скоро истекает срок", DAYS_HINT)
        self._caption(row, "за")
        self._days = TextField(
            width=DAYS_FIELD_WIDTH,
            justify="center",
            on_change=self._days_edited,
        )
        self._days.set(str(self._user.warning_days))
        row.addSpacing(4)
        row.addWidget(self._days)
        row.addSpacing(4)
        self._caption(row, "дней")

        row, _ = self._row(inner, "Низкий остаток", "Когда количество ≤ минимального")
        self._low = Toggle(self._user.notify_low_stock)
        row.addWidget(self._low)
        return card

    def _build_appearance(self) -> Card:
        card, inner = self._section("Оформление", "Внешний вид приложения")
        row, _ = self._row(inner, "Тема", first=True)
        names = [name for _key, name in THEMES]
        current = [key for key, _name in THEMES].index(self._user.theme)
        self._theme = Segmented(
            names,
            current,
            # Тема применяется сразу, без кнопки «Сохранить изменения».
            lambda index: self._shell.set_theme(THEMES[index][0]),
            variant="outline",
        )
        row.addWidget(self._theme)

        row, _ = self._row(inner, "Размер текста")
        sizes = list(theme.TEXT_SIZES)
        self._text_size = Segmented(
            [theme.TEXT_SIZES[key][0] for key in sizes],
            sizes.index(theme.text_size_name()),
            # Как и тема, размер текста применяется сразу.
            lambda index: self._shell.set_text_size(sizes[index]),
            variant="outline",
        )
        row.addWidget(self._text_size)
        return card

    @property
    def theme_switch(self) -> Segmented:
        """Выбор темы."""
        return self._theme

    @property
    def text_size_switch(self) -> Segmented:
        """Выбор размера текста."""
        return self._text_size

    @property
    def days_field(self) -> TextField:
        """Поле «за сколько дней предупреждать»."""
        return self._days

    @property
    def days_hint(self) -> QLabel:
        """Пояснение под «Скоро истекает срок» (показывает и ошибку поля)."""
        return self._days_hint

    @property
    def expired_toggle(self) -> Toggle:
        """Переключатель «Срок годности истёк»."""
        return self._expired

    @property
    def low_toggle(self) -> Toggle:
        """Переключатель «Низкий остаток»."""
        return self._low

    # --- сохранение ---

    def _days_edited(self) -> None:
        self._days.clear_error()
        self._days_hint.setText(DAYS_HINT)
        recolor(self._days_hint, "ink_3")

    def _clear_errors(self) -> None:
        for field in self._fields.values():
            field.clear_error()
        self._days_edited()

    def _save(self) -> None:
        """Сохраняет профиль, настройки и (если введён) новый пароль."""
        self._clear_errors()
        settings = self._services.settings
        user_id = self._user.id
        try:
            settings.update_profile(
                user_id,
                self._fields["username"].get(),
                self._fields["email"].get(),
            )
            settings.update_settings(
                user_id,
                self._days.get(),
                THEMES[self._theme.active][0],
                self._expired.value,
                self._low.value,
            )
            self._change_password_if_filled()
        except ValidationError as error:
            self._show_error(error)
            return
        except NotFoundError:
            self._shell.app.sign_out()
            return
        self._shell.app.apply_user_changes(settings.get_user(user_id), SAVED)

    def _change_password_if_filled(self) -> None:
        """Меняет пароль, если заполнено «Новый пароль» или его повтор.

        Текущий пароль для проверки берётся из сеанса, пользователь его не
        вводит: поле «Текущий пароль» только показывает его.
        """
        new = self._fields["new_password"].get()
        repeat = self._fields["new_password_repeat"].get()
        if not (new or repeat):
            return
        app = self._shell.app
        old = app.session_password or self._fields["old_password"].get()
        self._services.auth.change_password(self._user.id, old, new, repeat)
        app.session_password = new
        app.remembered.clear()

    def _show_error(self, error: ValidationError) -> None:
        if error.field == "warning_days":
            self._days.set_error()
            self._days_hint.setText(error.message)
            recolor(self._days_hint, "red")
            return
        field = self._fields.get(error.field or "")
        if field is not None:
            field.set_error(error.message)
            field.focus_field()

    def _cancel(self) -> None:
        self._shell.navigate(sections.SETTINGS)

    # --- уведомление «сохранено» ---

    def _show_notice(self, text: str) -> None:
        self._notice = Badge(text, "green", icon="check")
        self._header.actions.insertWidget(0, self._notice)
        self._header.actions.insertSpacing(1, 10)
        self._notice_timer.start()

    def _hide_notice(self) -> None:
        if self._notice is not None:
            self._notice.setVisible(False)
            self._notice.deleteLater()
            self._notice = None
