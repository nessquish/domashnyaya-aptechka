"""Тесты окна приложения и экранов входа и регистрации."""

import unittest

from PySide6.QtWidgets import QLabel, QWidget
from shiboken6 import isValid

from pharmacy.ui import theme
from pharmacy.ui.screens.auth import LoginScreen, RegisterScreen
from pharmacy.ui.screens.shell import MainShell
from tests.qt_helpers import AppTestCase, click, find_all, settle, type_text


class LoginScreenTest(AppTestCase):
    def fill(self, login, password):
        self.screen._fields["login"].set(login)
        self.screen._fields["password"].set(password)
        self.screen._submit()
        self.settle()

    def test_starts_on_login(self):
        self.assertIsInstance(self.screen, LoginScreen)
        self.assertIsNone(self.app.user)

    def test_window_has_design_size(self):
        self.assertEqual(self.app.minimumWidth(), theme.WINDOW_MIN_WIDTH)
        self.assertEqual(self.app.minimumHeight(), theme.WINDOW_MIN_HEIGHT)

    def test_successful_login(self):
        self.fill("anna", "password1")
        self.assertEqual(self.app.user.login, "anna")
        self.assertIsInstance(self.screen, MainShell)

    def test_wrong_password_shows_banner_and_marks_password(self):
        self.fill("anna", "wrong-password")
        self.assertIsInstance(self.screen, LoginScreen)
        self.assertEqual(self.screen._banner.text, "Неверный пароль")
        self.assertTrue(self.screen._banner.isVisible())
        self.assertIsNotNone(self.screen._fields["password"].error)
        # Аккаунт найден, поэтому логин не подсвечивается.
        self.assertIsNone(self.screen._fields["login"].error)
        self.assertEqual(
            self.screen._fields["password"].frame_colors()[0], theme.LIGHT.red
        )
        self.assertNotEqual(
            self.screen._fields["login"].frame_colors()[0], theme.LIGHT.red
        )
        self.assertIsNone(self.app.user)

    def test_known_email_with_wrong_password_marks_only_the_password(self):
        self.fill("anna@mail.ru", "wrong-password")
        self.assertEqual(self.screen._banner.text, "Неверный пароль")
        self.assertIsNone(self.screen._fields["login"].error)
        self.assertIsNotNone(self.screen._fields["password"].error)

    def test_unknown_login_or_email_marks_only_the_login(self):
        for text in ("nobody", "nobody@mail.ru"):
            self.app.show_login()
            self.settle()
            self.fill(text, "password1")
            self.assertEqual(
                self.screen._banner.text, "Аккаунт с таким логином или почтой не найден"
            )
            self.assertIsNotNone(self.screen._fields["login"].error, text)
            self.assertIsNone(self.screen._fields["password"].error, text)
            self.assertEqual(
                self.screen._fields["login"].frame_colors()[0], theme.LIGHT.red
            )

    def test_empty_login_marks_login_field(self):
        self.fill("", "password1")
        self.assertEqual(
            self.screen._fields["login"].error, "Введите логин или эл. почту"
        )

    def test_empty_password_marks_password_field(self):
        self.fill("anna", "")
        self.assertEqual(self.screen._fields["password"].error, "Введите пароль")

    def test_new_attempt_clears_previous_error(self):
        self.fill("anna", "wrong-password")
        self.fill("anna", "password1")
        self.assertIsInstance(self.screen, MainShell)

    def test_banner_is_hidden_after_a_good_attempt_starts(self):
        self.fill("anna", "wrong-password")
        self.screen._fields["password"].set("password1")
        self.screen._reset_errors()
        self.assertFalse(self.screen._banner.isVisible())
        self.assertEqual(self.screen._banner.text, "")

    def test_field_is_called_login_or_email(self):
        texts = [w.text() for w in find_all(self.screen, QLabel)]
        self.assertIn("Логин / Эл. почта", texts)

    def test_can_sign_in_with_the_email_instead_of_the_login(self):
        self.fill("anna@mail.ru", "password1")
        self.assertEqual(self.app.user.login, "anna")
        self.assertIsInstance(self.screen, MainShell)

    def test_email_is_matched_ignoring_case_and_spaces(self):
        self.fill("  Anna@Mail.RU ", "password1")
        self.assertIsInstance(self.screen, MainShell)

    def test_nothing_is_red_while_typing_or_leaving_the_fields(self):
        # Как в большинстве приложений: вход проверяется только по кнопке.
        for text in ("ab", "anna@mail", "my login", ""):
            self.app.show_login()
            self.settle()
            field = self.screen._fields["login"]
            type_text(field.entry, text)
            field.entry.focus_changed.emit(False)
            self.screen._fields["password"].entry.focus_changed.emit(False)
            self.assertIsNone(field.error, text)
            self.assertIsNone(self.screen._fields["password"].error, text)
            self.assertFalse(self.screen._banner.isVisible(), text)

    def test_odd_looking_login_is_checked_by_the_service_not_by_the_form(self):
        for text in ("ab", "anna@mail", "my login"):
            self.app.show_login()
            self.settle()
            self.fill(text, "password1")
            self.assertIsInstance(self.screen, LoginScreen)
            self.assertEqual(
                self.screen._banner.text, "Аккаунт с таким логином или почтой не найден"
            )
            self.assertIsNotNone(self.screen._fields["login"].error, text)

    def test_red_fields_clear_when_the_user_types_again(self):
        self.fill("nobody", "password1")
        self.assertIsNotNone(self.screen._fields["login"].error)
        type_text(self.screen._fields["login"].entry, "x")
        self.assertIsNone(self.screen._fields["login"].error)

    def test_link_opens_registration(self):
        click(self.screen.switch_link)
        self.settle()
        self.assertIsInstance(self.screen, RegisterScreen)

    def test_submit_button_logs_in(self):
        self.screen._fields["login"].set("anna")
        self.screen._fields["password"].set("password1")
        click(self.screen.submit_button)
        self.settle()
        self.assertIsInstance(self.screen, MainShell)

    def test_enter_in_a_field_submits(self):
        self.screen._fields["login"].set("anna")
        self.screen._fields["password"].set("password1")
        self.screen._fields["password"].entry.returnPressed.emit()
        self.settle()
        self.assertIsInstance(self.screen, MainShell)


class RegisterScreenTest(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.app.show_register()
        self.settle()

    def fill(self, **values):
        data = {
            "username": "Борис",
            "login": "boris",
            "email": "boris@mail.ru",
            "password": "password1",
            "password_repeat": "password1",
        }
        data.update(values)
        for key, value in data.items():
            self.screen._fields[key].set(value)
        self.screen._submit()
        self.settle()

    def test_successful_registration_signs_in(self):
        self.fill()
        self.assertEqual(self.app.user.login, "boris")
        self.assertIsInstance(self.screen, MainShell)

    def test_username_is_optional(self):
        self.fill(username="")
        self.assertEqual(self.app.user.username, "boris")

    def test_duplicate_login_is_marked_on_the_login_field(self):
        self.fill(login="anna", email="other@mail.ru")
        self.assertIsInstance(self.screen, RegisterScreen)
        self.assertEqual(self.screen._fields["login"].error, "Этот логин уже занят")

    def test_each_error_goes_to_its_own_field(self):
        cases = {
            "login": ("login", "ab"),
            "email": ("email", "bad"),
            "password": ("password", "short"),
            "password_repeat": ("password_repeat", "different"),
        }
        for key, (field, value) in cases.items():
            self.app.show_register()
            self.settle()
            values = {field: value}
            if key == "password":
                values["password_repeat"] = value
            self.fill(**values)
            self.assertIsNotNone(self.screen._fields[key].error, key)

    def test_password_mismatch_does_not_register(self):
        self.fill(password_repeat="other-password")
        self.assertIsNone(self.app.user)
        self.assertEqual(self.count_rows("users"), 1)

    def test_required_fields_are_marked(self):
        self.assertEqual(
            set(self.screen._fields),
            {"username", "login", "email", "password", "password_repeat"},
        )

    def test_link_returns_to_login(self):
        click(self.screen.switch_link)
        self.settle()
        self.assertIsInstance(self.screen, LoginScreen)


class EmailCheckTest(AppTestCase):
    """Проверка почты при регистрации: при уходе с поля, при вводе и по кнопке."""

    MESSAGE = "Введите корректный email, например user@gmail.com"

    def setUp(self) -> None:
        super().setUp()
        self.app.show_register()
        self.settle()
        self.field = self.screen._fields["email"]
        self.button = self.screen.submit_button

    def type_email(self, text: str) -> None:
        self.field.set("")
        type_text(self.field.entry, text)

    def leave(self) -> None:
        self.field.entry.focus_changed.emit(False)  # Qt сообщает так об уходе с поля

    def fill_others(self) -> None:
        for key, value in {
            "username": "Борис",
            "login": "boris",
            "password": "password1",
            "password_repeat": "password1",
        }.items():
            self.screen._fields[key].set(value)

    def test_button_is_disabled_until_the_email_is_valid(self):
        self.assertFalse(self.button.enabled)
        self.type_email("abc")
        self.assertFalse(self.button.enabled)
        self.type_email("abc@")
        self.assertFalse(self.button.enabled)
        self.type_email("abc@xyz")
        self.assertFalse(self.button.enabled)
        self.type_email("abc@xyz.ru")
        self.assertTrue(self.button.enabled)

    def test_button_turns_off_again_when_the_email_is_spoiled(self):
        self.type_email("abc@xyz.ru")
        self.assertTrue(self.button.enabled)
        type_text(self.field.entry, " x")  # пробел внутри адреса
        self.assertFalse(self.button.enabled)

    def test_leaving_a_bad_email_shows_the_error_under_the_field(self):
        self.type_email("abc@xyz")
        self.assertIsNone(self.field.error)  # пока печатал, не ругаемся
        self.leave()
        self.assertEqual(self.field.error, self.MESSAGE)
        self.assertTrue(self.field._error_label.isVisible())
        self.assertEqual(self.field._error_label.text(), self.MESSAGE)
        self.assertEqual(self.field.frame_colors()[0], theme.LIGHT.red)

    def test_leaving_an_empty_email_shows_the_error_too(self):
        self.leave()
        self.assertEqual(self.field.error, self.MESSAGE)

    def test_leaving_a_good_email_shows_nothing(self):
        for email in ("user@gmail.com", "a@mail.ru", "b@yandex.ru", "c@inbox.ru"):
            self.type_email(email)
            self.leave()
            self.assertIsNone(self.field.error, email)

    def test_error_disappears_as_soon_as_the_email_is_fixed(self):
        self.type_email("abc@xyz")
        self.leave()
        type_text(self.field.entry, ".ru")
        self.assertIsNone(self.field.error)
        self.assertTrue(self.button.enabled)

    def test_error_comes_back_while_typing_after_the_first_departure(self):
        self.type_email("abc@xyz.ru")
        self.leave()
        self.assertIsNone(self.field.error)
        type_text(self.field.entry, "@")
        self.assertEqual(self.field.error, self.MESSAGE)

    def test_moving_focus_to_another_field_triggers_the_check(self):
        self.type_email("abc")
        self.field.entry.setFocus()
        self.screen._fields["password"].entry.setFocus()
        self.settle()
        if self.field.error is None:  # без активного окна Qt не шлёт события фокуса
            self.leave()
        self.assertEqual(self.field.error, self.MESSAGE)

    def test_submit_with_a_bad_email_shows_the_error_and_does_not_register(self):
        self.fill_others()
        self.type_email("abc@xyz")
        self.screen._submit()
        self.settle()
        self.assertIsNone(self.app.user)
        self.assertEqual(self.field.error, self.MESSAGE)
        self.assertEqual(self.count_rows("users"), 1)

    def test_submit_with_an_empty_email_shows_the_error(self):
        self.fill_others()
        self.screen._submit()
        self.assertEqual(self.field.error, self.MESSAGE)
        self.assertIsNone(self.app.user)

    def test_enter_in_another_field_cannot_bypass_the_check(self):
        self.fill_others()
        self.type_email("abc")
        self.screen._fields["password"].entry.returnPressed.emit()
        self.settle()
        self.assertIsNone(self.app.user)
        self.assertEqual(self.field.error, self.MESSAGE)

    def test_clicking_the_disabled_button_does_nothing(self):
        self.fill_others()
        self.type_email("abc")
        click(self.button)
        self.settle()
        self.assertIsNone(self.app.user)

    def test_registration_works_with_a_valid_email(self):
        self.fill_others()
        self.type_email("boris@yandex.ru")
        self.assertTrue(self.button.enabled)
        click(self.button)
        self.settle()
        self.assertEqual(self.app.user.email, "boris@yandex.ru")

    def test_email_is_saved_in_lower_case(self):
        self.fill_others()
        self.type_email("Boris@Gmail.COM")
        self.screen._submit()
        self.assertEqual(self.app.user.email, "boris@gmail.com")

    def test_any_correct_domain_is_accepted(self):
        for email in ("x@university.edu", "y@my-firm.company", "z@sub.mail.co.uk"):
            self.type_email(email)
            self.assertTrue(self.button.enabled, email)

    def test_service_errors_still_appear_on_the_field(self):
        self.fill_others()
        self.type_email("anna@mail.ru")  # такая почта уже занята
        self.db.execute("UPDATE users SET email = 'anna@mail.ru'")
        self.screen._submit()
        self.settle()
        self.assertEqual(self.field.error, "Эта почта уже зарегистрирована")

    def test_login_screen_has_no_email_check(self):
        self.app.show_login()
        self.settle()
        self.assertTrue(self.screen.submit_button.enabled)

    # --- логин ---

    def login_field(self):
        return self.screen._fields["login"]

    def type_login(self, text: str) -> None:
        self.login_field().set("")
        type_text(self.login_field().entry, text)

    def leave_login(self) -> None:
        self.login_field().entry.focus_changed.emit(False)

    def test_bad_login_is_marked_red_when_the_user_leaves_the_field(self):
        for login in ("ab", "my login", "логин", "a" * 31, "ab!"):
            self.app.show_register()  # чистая форма: поле ещё не «тронуто»
            self.settle()
            self.type_login(login)
            self.assertIsNone(self.login_field().error, login)  # пока печатает
            self.leave_login()
            self.assertIsNotNone(self.login_field().error, login)
            self.assertTrue(self.login_field()._error_label.isVisible(), login)
            self.assertEqual(
                self.login_field().frame_colors()[0], theme.LIGHT.red, login
            )

    def test_login_error_text_explains_the_rule(self):
        self.type_login("ab")
        self.leave_login()
        self.assertIn("от 3 до 30 символов", self.login_field().error)

    def test_empty_login_asks_to_enter_it(self):
        self.leave_login()
        self.assertEqual(self.login_field().error, "Введите логин")

    def test_good_login_is_not_marked(self):
        for login in ("nessquish", "a.b-c_1", "abc"):
            self.type_login(login)
            self.leave_login()
            self.assertIsNone(self.login_field().error, login)

    def test_login_error_goes_away_when_fixed(self):
        self.type_login("ab")
        self.leave_login()
        type_text(self.login_field().entry, "c")
        self.assertIsNone(self.login_field().error)

    def test_login_error_comes_back_while_typing_after_leaving(self):
        self.type_login("abc")
        self.leave_login()
        type_text(self.login_field().entry, " d")
        self.assertIsNotNone(self.login_field().error)

    def test_bad_login_does_not_disable_the_button_by_itself(self):
        self.type_login("ab")
        self.type_email("abc@xyz.ru")
        self.assertTrue(self.button.enabled)

    def test_submit_marks_both_login_and_email_at_once(self):
        self.fill_others()
        self.type_login("ab")
        self.type_email("abc")
        self.screen._submit()
        self.assertIsNotNone(self.login_field().error)
        self.assertEqual(self.field.error, self.MESSAGE)
        self.assertIsNone(self.app.user)

    def test_submit_puts_the_cursor_into_the_first_wrong_field(self):
        self.fill_others()
        self.type_login("ab")
        self.type_email("abc")
        self.screen._submit()
        self.settle()
        self.assertEqual(self.count_rows("users"), 1)

    def test_good_login_and_email_register(self):
        self.fill_others()
        self.type_login("boris")
        self.type_email("boris@mail.ru")
        self.screen._submit()
        self.settle()
        self.assertEqual(self.app.user.login, "boris")

    def test_check_object_reports_the_state(self):
        self.type_email("abc@xyz.ru")
        self.assertTrue(self.screen._email_check.valid)
        self.type_email("abc")
        self.assertFalse(self.screen._email_check.valid)


class NavigationTest(AppTestCase):
    def sign_in(self):
        self.screen._fields["login"].set("anna")
        self.screen._fields["password"].set("password1")
        self.screen._submit()
        self.settle()

    def test_sign_out_returns_to_login_with_light_theme(self):
        self.sign_in()
        self.db.execute("UPDATE users SET theme = 'dark'")
        self.app.sign_out()
        self.assertIsInstance(self.screen, LoginScreen)
        self.assertIsNone(self.app.user)
        self.assertEqual(theme.theme_name(), "light")

    def test_user_theme_is_applied_on_sign_in(self):
        self.db.execute("UPDATE users SET theme = 'dark'")
        self.sign_in()
        self.assertEqual(theme.theme_name(), "dark")

    def test_screens_are_replaced_not_stacked(self):
        for _ in range(3):
            self.app.show_register()
            self.app.show_login()
        self.settle()
        shown = [
            w
            for w in self.app.centralWidget().findChildren(QWidget)
            if w.parent() is self.app.centralWidget()
        ]
        self.assertEqual(shown, [self.screen])

    def test_old_screen_is_deleted(self):
        old = self.screen
        self.app.show_register()
        self.settle()
        self.assertFalse(isValid(old))  # Qt удалил виджет, а не только спрятал

    def test_session_password_is_kept_only_in_memory(self):
        self.sign_in()
        self.assertEqual(self.app.session_password, "password1")
        self.app.sign_out()
        self.assertEqual(self.app.session_password, "")

    def test_window_title_and_icon(self):
        self.assertEqual(self.app.windowTitle(), "Моя аптечка")
        self.assertFalse(self.app.windowIcon().isNull())

    def test_closing_leaves_nothing_visible(self):
        self.app.close()
        settle()
        self.assertFalse(self.app.isVisible())


if __name__ == "__main__":
    unittest.main()
