"""Бизнес-логика работы с товарами аптечки."""

import math
from dataclasses import dataclass, field, replace
from datetime import date
from typing import List, Optional, Sequence

from pharmacy.db.connection import Database
from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.models import Category, HistoryAction, Product, ProductData
from pharmacy.repositories.category_repository import CategoryRepository
from pharmacy.repositories.history_repository import HistoryRepository
from pharmacy.repositories.product_repository import ProductRepository
from pharmacy.repositories.user_repository import UserRepository
from pharmacy.services.notification_service import NotificationService
from pharmacy.services.status import (
    STATUS_PRIORITY,
    ProductStatus,
    primary_status,
    product_statuses,
)
from pharmacy.utils.dates import days_until, parse_user_date
from pharmacy.utils.formatting import format_quantity
from pharmacy.utils.units import normalize_unit

MAX_NAME_LENGTH = 100
MAX_SHORT_TEXT_LENGTH = 100
MAX_LONG_TEXT_LENGTH = 500
MAX_AMOUNT = 1_000_000


@dataclass
class ProductForm:
    """Данные формы товара в том виде, как их ввёл пользователь (текстом).

    Attributes:
        name: Название.
        category_id: Выбранная категория.
        quantity: Количество (можно с запятой: ``1,5``).
        unit: Единица измерения.
        expiry_date: Срок годности в виде ДД.ММ.ГГГГ или пустая строка.
        indications: Показания или назначение.
        storage_place: Место хранения.
        min_quantity: Минимальный остаток (пусто означает 0).
        note: Примечание.
    """

    name: str = ""
    category_id: Optional[int] = None
    quantity: str = ""
    unit: str = ""
    expiry_date: str = ""
    indications: str = ""
    storage_place: str = ""
    min_quantity: str = ""
    note: str = ""


@dataclass
class ProductView:
    """Товар вместе с рассчитанными состояниями, готовый к показу.

    Attributes:
        product: Сам товар.
        statuses: Все состояния товара, от самого важного.
        days_left: Сколько дней до конца срока (отрицательное, если срок
            прошёл) или None, если срок не указан.
    """

    product: Product
    statuses: List[ProductStatus] = field(default_factory=list)
    days_left: Optional[int] = None

    @property
    def primary_status(self) -> ProductStatus:
        """Главное состояние, которое показывается в таблице."""
        return primary_status(self.statuses)


def _parse_amount(text: str, field_name: str, empty_message: Optional[str]) -> float:
    """Разбирает число из формы.

    Args:
        text: Введённый текст (допустима запятая как разделитель).
        field_name: Имя поля формы для сообщения об ошибке.
        empty_message: Сообщение, если поле пустое. Если None, пустое
            поле означает 0.

    Returns:
        Неотрицательное число.

    Raises:
        ValidationError: Если введено не число, оно отрицательное или слишком большое.
    """
    cleaned = text.strip().replace(",", ".")
    if not cleaned:
        if empty_message is not None:
            raise ValidationError(empty_message, field_name)
        return 0.0
    try:
        value = float(cleaned)
    except ValueError:
        raise ValidationError("Введите число, например 2 или 1,5", field_name) from None
    if not math.isfinite(value):
        raise ValidationError("Введите число, например 2 или 1,5", field_name)
    if value < 0:
        raise ValidationError("Значение не может быть отрицательным", field_name)
    if value > MAX_AMOUNT:
        raise ValidationError("Слишком большое значение", field_name)
    return value


def _check_length(text: str, limit: int, label: str, field_name: str) -> str:
    """Убирает пробелы по краям и проверяет, что текст не длиннее лимита."""
    text = text.strip()
    if len(text) > limit:
        raise ValidationError(f"{label}: не больше {limit} символов", field_name)
    return text


def _to_data(product: Product) -> ProductData:
    """Данные товара в виде, готовом к записи (чтобы изменить одно поле)."""
    return ProductData(
        name=product.name,
        category_id=product.category_id,
        quantity=product.quantity,
        unit=product.unit,
        expiry_date=product.expiry_date,
        indications=product.indications,
        storage_place=product.storage_place,
        min_quantity=product.min_quantity,
        note=product.note,
    )


def _describe_changes(old: Product, new: ProductData) -> str:
    """Описывает, что изменилось в товаре (для записи в историю).

    Args:
        old: Товар до изменения.
        new: Новые данные товара.

    Returns:
        Текст вида «количество изменено с 5 до 10; изменено: срок годности»
        или пустая строка, если ничего не изменилось.
    """
    parts = []
    if old.quantity != new.quantity:
        parts.append(
            f"количество изменено с {format_quantity(old.quantity)} {old.unit}"
            f" до {format_quantity(new.quantity)} {new.unit}"
        )
    if old.min_quantity != new.min_quantity:
        parts.append(
            f"минимальный остаток изменён с {format_quantity(old.min_quantity)}"
            f" {old.unit} до {format_quantity(new.min_quantity)} {new.unit}"
        )
    other = [
        label
        for label, changed in (
            ("название", old.name != new.name),
            ("категория", old.category_id != new.category_id),
            ("единица измерения", old.unit != new.unit),
            ("срок годности", old.expiry_date != new.expiry_date),
            ("место хранения", old.storage_place != new.storage_place),
            ("показания", old.indications != new.indications),
            ("примечание", old.note != new.note),
        )
        if changed
    ]
    if other:
        parts.append("изменено: " + ", ".join(other))
    return "; ".join(parts)


SORT_STATUS = "status"  # сначала просроченные, ниже остальные, в конце норма
SORT_STATUS_OK = "status_ok"  # сначала норма, в конце просроченные


def sort_by_status(
    views: List[ProductView], problems_first: bool = True
) -> List[ProductView]:
    """Сортирует товары по состоянию, а внутри группы по сроку годности.

    Ключ сортировки это пара «номер состояния, срок годности». Направление
    меняется только у номера состояния: внутри группы самые старые сроки
    всегда сверху, а товары без срока в конце группы.

    Args:
        views: Товары (уже упорядочены по сроку годности).
        problems_first: True: просроченные сверху, норма снизу; False: наоборот.

    Returns:
        Новый список в нужном порядке.
    """
    rank = {status: number for number, status in enumerate(STATUS_PRIORITY)}
    last = len(STATUS_PRIORITY) - 1

    def key(view: ProductView) -> tuple:
        number = rank[view.primary_status]
        expiry = view.product.expiry_date
        return (
            number if problems_first else last - number,
            expiry is None,
            expiry or date.max,
            view.product.name.casefold(),
        )

    return sorted(views, key=key)


class ProductService:
    """Добавление, изменение, удаление и просмотр товаров пользователя."""

    def __init__(
        self,
        db: Database,
        notifications: Optional[NotificationService] = None,
    ) -> None:
        """Создаёт сервис.

        Args:
            db: Менеджер базы данных.
            notifications: Сервис уведомлений. Если передан, после добавления
                и изменения товара его уведомления пересчитываются.
        """
        self._db = db
        self._notifications = notifications
        self._products = ProductRepository(db)
        self._categories = CategoryRepository(db)
        self._history = HistoryRepository(db)
        self._users = UserRepository(db)

    def _refresh_notifications(self, user_id: int, product_id: int) -> None:
        """Пересчитывает уведомления товара, если подключён сервис уведомлений."""
        if self._notifications is not None:
            self._notifications.refresh(user_id, product_id=product_id)

    def list_categories(self) -> List[Category]:
        """Возвращает категории для выпадающего списка."""
        return self._categories.list_all()

    def add_product(self, user_id: int, form: ProductForm) -> ProductView:
        """Добавляет товар и записывает это в историю.

        Args:
            user_id: Владелец товара.
            form: Данные формы.

        Returns:
            Добавленный товар.

        Raises:
            ValidationError: Если данные формы неверны.
        """
        data = self._validate(form)
        with self._db.transaction() as conn:
            product_id = self._products.add(user_id, data, conn)
            self._history.add(
                user_id,
                product_id,
                HistoryAction.PRODUCT_ADDED,
                f"{data.name} · добавлен в аптечку",
                conn,
            )
        self._refresh_notifications(user_id, product_id)
        return self.get_product(user_id, product_id)

    def update_product(
        self, user_id: int, product_id: int, form: ProductForm
    ) -> ProductView:
        """Изменяет товар. Если что-то изменилось, записывает это в историю.

        Args:
            user_id: Владелец товара.
            product_id: Идентификатор товара.
            form: Новые данные формы.

        Returns:
            Обновлённый товар.

        Raises:
            NotFoundError: Если товара нет или он принадлежит другому пользователю.
            ValidationError: Если данные формы неверны.
        """
        old = self._require_product(user_id, product_id)
        data = self._validate(form)
        changes = _describe_changes(old, data)
        with self._db.transaction() as conn:
            self._products.update(user_id, product_id, data, conn)
            if changes:
                self._history.add(
                    user_id,
                    product_id,
                    HistoryAction.PRODUCT_UPDATED,
                    f"{data.name} · {changes}",
                    conn,
                )
        self._refresh_notifications(user_id, product_id)
        return self.get_product(user_id, product_id)

    def delete_product(self, user_id: int, product_id: int) -> None:
        """Удаляет товар и записывает это в историю.

        Название товара сохраняется в описании записи: сам товар из базы
        исчезает, а история остаётся.

        Args:
            user_id: Владелец товара.
            product_id: Идентификатор товара.

        Raises:
            NotFoundError: Если товара нет или он принадлежит другому пользователю.
        """
        product = self._require_product(user_id, product_id)
        with self._db.transaction() as conn:
            self._history.add(
                user_id,
                None,
                HistoryAction.PRODUCT_DELETED,
                f"{product.name} · удалён из аптечки",
                conn,
            )
            self._products.delete(user_id, product_id, conn)

    def delete_products(self, user_id: int, product_ids: Sequence[int]) -> int:
        """Удаляет несколько товаров. Чужие и уже удалённые пропускаются.

        Returns:
            Сколько товаров удалено.
        """
        deleted = 0
        for product_id in product_ids:
            try:
                self.delete_product(user_id, product_id)
            except NotFoundError:
                continue
            deleted += 1
        return deleted

    def change_category(
        self, user_id: int, product_ids: Sequence[int], category_id: int
    ) -> int:
        """Переносит несколько товаров в другую категорию.

        Каждое изменение записывается в историю, как обычное редактирование.

        Returns:
            Сколько товаров перенесено (те, что уже в этой категории, не считаются).

        Raises:
            ValidationError: Если такой категории нет.
        """
        if self._categories.get(category_id) is None:
            raise ValidationError("Выберите категорию", "category_id")
        changed = 0
        for product_id in product_ids:
            old = self._products.get(user_id, product_id)
            if old is None or old.category_id == category_id:
                continue
            data = replace(_to_data(old), category_id=category_id)
            with self._db.transaction() as conn:
                self._products.update(user_id, product_id, data, conn)
                self._history.add(
                    user_id,
                    product_id,
                    HistoryAction.PRODUCT_UPDATED,
                    f"{old.name} · {_describe_changes(old, data)}",
                    conn,
                )
            changed += 1
        return changed

    def search_products(
        self, user_id: int, query: str, limit: int = 10
    ) -> List[Product]:
        """Ищет товары по названию, категории и примечанию (для поиска по программе).

        Сначала идут товары, у которых название начинается с запроса, затем те,
        где запрос внутри названия, и последними совпавшие по категории или
        примечанию. Регистр букв не важен.

        Args:
            user_id: Владелец товаров.
            query: Введённый текст.
            limit: Сколько товаров вернуть не больше.
        """
        needle = query.strip().casefold()
        if not needle:
            return []
        ranked = []
        for product in self._products.list_for_user(user_id):
            name = product.name.casefold()
            if name.startswith(needle):
                rank = 0
            elif needle in name:
                rank = 1
            elif (
                needle in (product.category_name or "").casefold()
                or needle in (product.note or "").casefold()
            ):
                rank = 2
            else:
                continue
            ranked.append((rank, name, product))
        ranked.sort(key=lambda item: (item[0], item[1]))
        return [product for _rank, _name, product in ranked[:limit]]

    def get_product(
        self, user_id: int, product_id: int, today: Optional[date] = None
    ) -> ProductView:
        """Возвращает товар с состояниями.

        Args:
            user_id: Владелец товара.
            product_id: Идентификатор товара.
            today: Сегодняшняя дата (по умолчанию из системы).

        Returns:
            Товар для показа в карточке.

        Raises:
            NotFoundError: Если товара нет или он принадлежит другому пользователю.
        """
        product = self._require_product(user_id, product_id)
        return self._view(product, self._warning_days(user_id), today)

    def list_products(
        self,
        user_id: int,
        search: str = "",
        category_id: Optional[int] = None,
        status: Optional[ProductStatus] = None,
        sort: str = "name",
        today: Optional[date] = None,
    ) -> List[ProductView]:
        """Возвращает товары пользователя для таблицы «Моя аптечка».

        Args:
            user_id: Владелец товаров.
            search: Часть названия (регистр не важен).
            category_id: Показать только эту категорию.
            status: Показать только товары в этом состоянии.
            sort: Сортировка: ``name``, ``expiry``, ``quantity``, ``added`` или
                по состоянию: ``status`` (сначала просроченные) и ``status_ok``
                (сначала норма). Внутри одной группы товары идут по сроку
                годности: самые старые сверху.
            today: Сегодняшняя дата (по умолчанию из системы).

        Returns:
            Список товаров с состояниями.
        """
        warning_days = self._warning_days(user_id)
        by_status = sort in (SORT_STATUS, SORT_STATUS_OK)
        views = [
            self._view(product, warning_days, today)
            for product in self._products.list_for_user(
                user_id, search, category_id, "expiry" if by_status else sort
            )
        ]
        if status is not None:
            views = [view for view in views if status in view.statuses]
        if by_status:
            views = sort_by_status(views, problems_first=sort == SORT_STATUS)
        return views

    def _view(
        self, product: Product, warning_days: int, today: Optional[date]
    ) -> ProductView:
        """Собирает ProductView: товар, его состояния и дни до конца срока."""
        days_left = None
        if product.expiry_date is not None:
            days_left = days_until(product.expiry_date, today)
        return ProductView(
            product=product,
            statuses=product_statuses(product, warning_days, today),
            days_left=days_left,
        )

    def _warning_days(self, user_id: int) -> int:
        """Возвращает настройку «за сколько дней предупреждать» пользователя."""
        user = self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Пользователь не найден")
        return user.warning_days

    def _require_product(self, user_id: int, product_id: int) -> Product:
        """Возвращает товар пользователя или выбрасывает NotFoundError."""
        product = self._products.get(user_id, product_id)
        if product is None:
            raise NotFoundError("Товар не найден")
        return product

    def _validate(self, form: ProductForm) -> ProductData:
        """Проверяет форму товара и превращает её в готовые данные.

        Args:
            form: Данные формы.

        Returns:
            Проверенные данные для записи в базу.

        Raises:
            ValidationError: С указанием поля, в котором найдена ошибка.
        """
        name = form.name.strip()
        if not name:
            raise ValidationError("Введите название", "name")
        name = _check_length(name, MAX_NAME_LENGTH, "Название", "name")
        if form.category_id is None or self._categories.get(form.category_id) is None:
            raise ValidationError("Выберите категорию", "category_id")
        quantity = _parse_amount(form.quantity, "quantity", "Введите количество")
        # Единица не указана: «шт.»; разные написания сводятся к одному.
        unit = normalize_unit(form.unit)
        min_quantity = _parse_amount(form.min_quantity, "min_quantity", None)
        return ProductData(
            name=name,
            category_id=form.category_id,
            quantity=quantity,
            unit=unit,
            expiry_date=self._parse_expiry(form.expiry_date),
            indications=_check_length(
                form.indications, MAX_LONG_TEXT_LENGTH, "Показания", "indications"
            ),
            storage_place=_check_length(
                form.storage_place,
                MAX_SHORT_TEXT_LENGTH,
                "Место хранения",
                "storage_place",
            ),
            min_quantity=min_quantity,
            note=_check_length(form.note, MAX_LONG_TEXT_LENGTH, "Примечание", "note"),
        )

    @staticmethod
    def _parse_expiry(text: str) -> Optional[date]:
        """Разбирает срок годности из формы (пусто означает «не указан»)."""
        if not text.strip():
            return None
        try:
            return parse_user_date(text)
        except ValueError:
            raise ValidationError(
                "Введите дату в формате ДД.ММ.ГГГГ", "expiry_date"
            ) from None
