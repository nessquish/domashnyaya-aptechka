"""Экраны входа и регистрации (макет Figma, экраны 01 и 02)."""

import math
from typing import TYPE_CHECKING, Callable, Dict, Sequence, Tuple

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pharmacy.errors import AuthenticationError, ValidationError
from pharmacy.ui.icons import icon_pixmap
from pharmacy.ui.widgets.banner import ErrorBanner
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.common import label, pad
from pharmacy.ui.widgets.controls import Checkbox
from pharmacy.ui.widgets.field import TextField
from pharmacy.ui.widgets.link import Link
from pharmacy.ui import theme
from pharmacy.ui.field_check import LiveCheck, email_error, login_error
from pharmacy.ui.theme import SHADOW_PAD, mix, palette

if TYPE_CHECKING:
    from pharmacy.ui.app import App

HERO_STRETCH = 44  # левая панель занимает 44% окна, форма остальное
FORM_STRETCH = 56
HERO_TEXT_WIDTH = 270
HERO_ICON_SIZE = 60
FORM_WIDTH = 440
FORM_PADDING_X = 44
GRADIENT_ANGLE = 160.0
HERO_SOFTEN = 0.6  # доля цвета фона в цветах градиента: чем больше, тем слабее
FADE_SHARE = 0.5  # какая часть левой панели справа уходит в цвет фона
CHECK_SIZE = 14
CHECK_GAP = 8
POINT_GAP = 9


class _HeroPanel(QWidget):
    """Левая панель с градиентом: знак, название, описание и преимущества."""

    def __init__(self, description: str, points: Sequence[str]) -> None:
        super().__init__()
        pal = palette()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)
        icon = QLabel()
        icon.setPixmap(icon_pixmap("cross", HERO_ICON_SIZE, pal.primary))
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(18)
        title = label("Моя аптечка", "display", "brand_ink", bare=True)
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        text = label(description, "lead", "ink_2", wrap=True, bare=True)
        text.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        text.setFixedWidth(HERO_TEXT_WIDTH)
        text.setMinimumHeight(text.heightForWidth(HERO_TEXT_WIDTH))
        layout.addWidget(text, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(26)
        layout.addWidget(self._points(points), 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    @staticmethod
    def _points(points: Sequence[str]) -> QWidget:
        """Список преимуществ с галочками, выровненный по левому краю."""
        host = QWidget()
        column = QVBoxLayout(host)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(POINT_GAP)
        check = icon_pixmap("check", CHECK_SIZE, palette().primary, 2.5)
        for point in points:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(CHECK_GAP)
            mark = QLabel()
            mark.setPixmap(check)
            mark.setFixedSize(CHECK_SIZE, CHECK_SIZE)
            row.addWidget(mark)
            row.addWidget(label(point, "body", "ink_2", bare=True))
            row.addStretch(1)
            column.addLayout(row)
        return host

    def paintEvent(self, _event) -> None:
        pal = palette()
        width, height = self.width(), self.height()
        radians = math.radians(GRADIENT_ANGLE)
        dx, dy = math.sin(radians), -math.cos(radians)
        length = abs(width * dx) + abs(height * dy)
        center = QPointF(width / 2, height / 2)
        shift = QPointF(dx * length / 2, dy * length / 2)
        gradient = QLinearGradient(center - shift, center + shift)
        # Градиент едва заметный: цвета панели ближе к фону окна.
        gradient.setColorAt(0, QColor(mix(pal.hero_from, pal.bg, HERO_SOFTEN)))
        gradient.setColorAt(1, QColor(mix(pal.hero_to, pal.bg, HERO_SOFTEN)))
        painter = QPainter(self)
        painter.fillRect(self.rect(), gradient)
        # Плавный переход к фону правой половины, без резкой границы.
        fade_start = width * (1 - FADE_SHARE)
        fade = QLinearGradient(QPointF(fade_start, 0), QPointF(width, 0))
        clear = QColor(pal.bg)
        clear.setAlpha(0)
        fade.setColorAt(0, clear)
        fade.setColorAt(1, QColor(pal.bg))
        painter.fillRect(self.rect(), fade)


class _AuthScreen(QWidget):
    """Общая раскладка: слева панель с описанием, справа карточка с формой."""

    def __init__(
        self,
        app: "App",
        description: str,
        points: Sequence[str],
        title: str,
        subtitle: str,
        padding_y: int,
        header_gaps: Tuple[int, int, int],
    ) -> None:
        super().__init__()
        pal = palette()
        self._app = app
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(_HeroPanel(description, points), HERO_STRETCH)
        area = QVBoxLayout()
        area.setContentsMargins(0, 0, 0, 0)
        card = Card(radius=theme.MODAL_RADIUS, elevated=True)
        area.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        row.addLayout(area, FORM_STRETCH)
        # Нарисованные виджеты (поля, кнопка) шире своей видимой части на поле
        # под тень, поэтому боковой отступ уменьшен, а обычные тексты сдвинуты.
        box = QWidget()
        box.setFixedWidth(FORM_WIDTH)
        card.body.addWidget(box)
        self._form = QVBoxLayout(box)
        self._form.setContentsMargins(
            FORM_PADDING_X - SHADOW_PAD,
            padding_y,
            FORM_PADDING_X - SHADOW_PAD,
            padding_y,
        )
        self._form.setSpacing(0)
        brand_gap, title_gap, subtitle_gap = header_gaps
        self._header("Моя аптечка", "brand", "primary", brand_gap)
        self._header(title, "heading", "ink", title_gap)
        self._header(subtitle, "body", "ink_2", subtitle_gap)
        self._banner = ErrorBanner(gap_below=14)
        self._form.addWidget(self._banner)
        self._fields: Dict[str, TextField] = {}
        self.setAutoFillBackground(False)
        self.backdrop_color = pal.bg

    def _header(self, text: str, style: str, color: str, gap_below: int) -> None:
        """Добавляет строку заголовка формы."""
        title = label(text, style, color)
        pad(title, SHADOW_PAD, 0, SHADOW_PAD, 0)
        self._form.addWidget(title)
        self._form.addSpacing(gap_below)

    def _add_field(self, key: str, field: TextField, gap: int) -> TextField:
        """Добавляет поле в форму и запоминает его под именем из сервиса."""
        self._form.addWidget(field)
        self._form.addSpacing(gap)
        field.bind_submit(self._submit)
        self._fields[key] = field
        return field

    def _add_footer(
        self, button_text: str, question: str, link: str, command: Callable[[], None]
    ) -> None:
        """Добавляет главную кнопку и строку «Нет аккаунта? Зарегистрироваться»."""
        self._form.addSpacing(2)
        self.submit_button = Button(
            button_text, self._submit, variant="primary", size="lg"
        )
        self._form.addWidget(self.submit_button)
        self._form.addSpacing(10)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch(1)
        row.addWidget(label(question, "small", "ink_2"))
        self.switch_link = Link(" " + link, command)
        row.addWidget(self.switch_link)
        row.addStretch(1)
        self._form.addLayout(row)

    def _reset_errors(self) -> None:
        self._banner.hide_message()
        for field in self._fields.values():
            field.clear_error()

    def _show_banner(self, message: str) -> None:
        """Показывает сообщение над первым полем формы."""
        self._banner.show_message(message)

    def _show_validation_error(self, error: ValidationError) -> None:
        """Показывает ошибку под нужным полем, а если поля нет, над формой."""
        field = self._fields.get(error.field or "")
        if field is None:
            self._show_banner(error.message)
            return
        field.set_error(error.message)
        field.focus_field()

    def _submit(self) -> None:
        raise NotImplementedError


class LoginScreen(_AuthScreen):
    """Вход по логину и паролю."""

    def __init__(self, app: "App") -> None:
        super().__init__(
            app,
            description="Удобный учёт ваших запасов лекарств и бытовых средств",
            points=(
                "Контроль сроков годности",
                "Уведомления о заканчивающихся товарах",
                "Список покупок в один клик",
            ),
            title="Вход в систему",
            subtitle="Введите свои данные, чтобы продолжить",
            padding_y=44,
            header_gaps=(18, 6, 20),
        )
        self._add_field("login", TextField("Логин / Эл. почта"), gap=8)
        self._add_field("password", TextField("Пароль", password=True), gap=8)
        self._add_remember()
        self._add_footer(
            "Войти", "Нет аккаунта?", "Зарегистрироваться", app.show_register
        )
        self._fields["login"].focus_field()

    def _add_remember(self) -> None:
        """Добавляет галочку «Запомнить это устройство 30 дней»."""
        row = QHBoxLayout()
        row.setContentsMargins(SHADOW_PAD, 2, SHADOW_PAD, 0)
        row.setSpacing(8)
        self._remember = Checkbox(False)
        row.addWidget(self._remember)
        row.addWidget(label("Запомнить это устройство 30 дней", "small", "ink_2"))
        row.addStretch(1)
        self._form.addLayout(row)
        self._form.addSpacing(10)

    def _submit(self) -> None:
        self._reset_errors()
        password = self._fields["password"].get()
        try:
            user = self._app.services.auth.login(self._fields["login"].get(), password)
        except ValidationError as error:
            self._show_validation_error(error)
        except AuthenticationError as error:
            self._show_banner(str(error))
            # Красным только то поле, где ошибка: если аккаунт найден, а пароль
            # неверный, логин или почту не трогаем.
            self._fields[error.field or "password"].set_error()
            self._fields[error.field or "password"].focus_field()
        else:
            self._app.sign_in(user, password, self._remember.value)


class RegisterScreen(_AuthScreen):
    """Создание аккаунта."""

    def __init__(self, app: "App") -> None:
        super().__init__(
            app,
            description="Создайте аккаунт для управления домашними запасами",
            points=(
                "Данные хранятся локально на компьютере",
                "Пароль хранится в зашифрованном виде",
            ),
            title="Создание аккаунта",
            subtitle="Заполните данные для регистрации",
            padding_y=24,
            header_gaps=(12, 6, 14),
        )
        gap = 5
        self._add_field(
            "username",
            TextField("Имя пользователя", placeholder="Введите имя"),
            gap,
        )
        self._add_field(
            "login",
            TextField("Логин", placeholder="Введите логин", required=True),
            gap,
        )
        self._add_field(
            "email",
            TextField(
                "Электронная почта", placeholder="example@mail.ru", required=True
            ),
            gap,
        )
        self._add_field(
            "password",
            TextField(
                "Пароль",
                placeholder="Не менее 8 символов",
                required=True,
                password=True,
            ),
            gap,
        )
        self._add_field(
            "password_repeat",
            TextField(
                "Повторите пароль",
                placeholder="Повторите пароль",
                required=True,
                password=True,
            ),
            gap,
        )
        self._add_footer(
            "Зарегистрироваться", "Уже есть аккаунт?", "Войти", app.show_login
        )
        # Логин и почта подсвечиваются красным, если записаны неверно. Кнопка
        # недоступна, пока в поле почты не корректный адрес.
        self._login_check = LiveCheck(self._fields["login"], login_error)
        self._email_check = LiveCheck(
            self._fields["email"], email_error, self.submit_button.set_enabled
        )
        self._fields["username"].focus_field()

    def _submit(self) -> None:
        self._reset_errors()
        checks = (
            ("login", self._login_check.check()),
            ("email", self._email_check.check()),
        )
        wrong = [key for key, correct in checks if not correct]
        if wrong:  # ошибки показаны под полями, курсор в первое неверное
            self._fields[wrong[0]].focus_field()
            return
        values = {key: field.get() for key, field in self._fields.items()}
        try:
            user = self._app.services.auth.register(
                login=values["login"],
                username=values["username"],
                email=values["email"],
                password=values["password"],
                password_repeat=values["password_repeat"],
            )
        except ValidationError as error:
            self._show_validation_error(error)
        else:
            self._app.sign_in(user, values["password"])
