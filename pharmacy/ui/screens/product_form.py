"""Форма товара: окно добавления и редактирования (макет Figma, экраны 05 и 07)."""

from datetime import date
from typing import Callable, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QWidget

from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.services.container import Services
from pharmacy.services.product_service import ProductForm, ProductView
from pharmacy.ui.theme import SHADOW_PAD
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.common import label
from pharmacy.ui.widgets.dialog import Modal
from pharmacy.ui.widgets.field import TextField
from pharmacy.ui.widgets.select import Select
from pharmacy.utils.dates import format_created, format_user_date
from pharmacy.utils.formatting import format_quantity
from pharmacy.utils.units import DEFAULT_UNIT, UNITS

COLUMN_GAP = 18
ROW_GAP = 14
DIALOG_WIDTH = 720
DIALOG_COLUMNS = 3
ADD_TITLE = "Добавить товар в аптечку"
EDIT_TITLE = "Редактирование товара"


def make_fields(services: Services, change: Callable[[], None]) -> Dict[str, QWidget]:
    """Создаёт поля формы товара в том порядке, в котором они стоят на экране.

    Args:
        services: Сервисы приложения (нужны категории).
        change: Вызывается после каждой правки пользователем.

    Returns:
        Поля по именам из ``ProductForm``.
    """
    categories = [(c.id, c.name) for c in services.products.list_categories()]

    def text(title: str, **options) -> TextField:
        return TextField(title, on_change=change, **options)

    fields: Dict[str, QWidget] = {}

    def unit_picked(_value: object) -> None:
        show_units(fields)
        change()

    fields.update(
        {
            "name": text("Название", placeholder="Введите название", required=True),
            "category_id": Select(
                categories,
                categories[0][0] if categories else None,
                label_text="Категория",
                required=True,
                on_change=lambda _value: change(),
            ),
            "quantity": text("Количество", placeholder="0", required=True),
            "unit": Select(
                UNITS,
                DEFAULT_UNIT,
                label_text="Единица измерения",
                required=True,
                on_change=unit_picked,
            ),
            "expiry_date": text(
                "Срок годности", placeholder="ДД.ММ.ГГГГ", trailing_icon="calendar"
            ),
            "storage_place": text(
                "Место хранения", placeholder="Например: шкаф, кухня"
            ),
            "min_quantity": text(
                "Минимальный остаток",
                placeholder="При меньшем количестве придёт уведомление",
            ),
            "indications": text(
                "Показания / назначение", placeholder="Например: жаропонижающее"
            ),
            "note": text(
                "Примечание", placeholder="Введите примечание", multiline=True
            ),
        }
    )
    show_units(fields)
    return fields


def show_units(fields: Dict[str, QWidget]) -> None:
    """Дописывает выбранную единицу к подписям «Количество» и «Минимальный остаток».

    Так рядом с числом всегда видно, в чём оно измеряется.
    """
    unit = fields["unit"].get() or DEFAULT_UNIT
    fields["quantity"].set_title(f"Количество ({unit})")
    fields["min_quantity"].set_title(f"Минимальный остаток ({unit})")


def read_form(fields: Dict[str, QWidget]) -> ProductForm:
    """Собирает введённые значения в форму для сервиса."""
    return ProductForm(**{key: widget.get() for key, widget in fields.items()})


def show_error(fields: Dict[str, QWidget], error: ValidationError) -> None:
    """Подсвечивает поле, к которому относится ошибка проверки."""
    field = fields.get(error.field or "")
    if field is not None:
        field.set_error(error.message)


def has_error(fields: Dict[str, QWidget]) -> bool:
    """Подсвечено ли ошибкой хотя бы одно поле."""
    return any(widget.error is not None for widget in fields.values())


class ProductFormDialog(Modal):
    """Окно добавления или редактирования товара поверх текущего экрана.

    Без ``product_id`` открывается «Добавить товар в аптечку», с ним
    «Редактирование товара» с уже заполненными полями.

    Attributes:
        fields: Поля формы по именам из ``ProductForm``.
        added_field: Дата добавления (только показывается, ставится сама).
        editing: Редактируется существующий товар.
    """

    def __init__(
        self,
        host: QWidget,
        services: Services,
        user_id: int,
        on_saved: Callable[[ProductView], None],
        product_id: Optional[int] = None,
    ) -> None:
        """Открывает окно.

        Args:
            host: Окно приложения.
            services: Сервисы приложения.
            user_id: Владелец аптечки.
            on_saved: Вызывается с сохранённым товаром (окно уже закрыто).
            product_id: Редактируемый товар или None для нового.

        Raises:
            NotFoundError: Если редактируемого товара нет.
        """
        existing = None
        if product_id is not None:
            existing = services.products.get_product(user_id, product_id)
        super().__init__(host, DIALOG_WIDTH, on_enter=self._submit)
        self._services = services
        self._user_id = user_id
        self._on_saved = on_saved
        self._product_id = product_id
        self._on_cancel: Optional[Callable[[], None]] = None
        self.editing = existing is not None
        self.add_title(EDIT_TITLE if self.editing else ADD_TITLE)
        self.fields = make_fields(services, self._refresh_save)
        self.added_field = TextField(
            "Дата добавления", readonly=True, trailing_icon="calendar"
        )
        self.added_field.set(format_user_date(date.today()))
        if existing is not None:
            self._fill(existing)
        self.body.addLayout(self._build_grid())
        self.body.addSpacing(8)
        self.body.addLayout(self._build_footer())
        self.fields["name"].focus_field()

    def _fill(self, view: ProductView) -> None:
        product = view.product
        values = {
            "name": product.name,
            "category_id": product.category_id,
            "quantity": format_quantity(product.quantity),
            "unit": product.unit,
            "expiry_date": format_user_date(product.expiry_date),
            "storage_place": product.storage_place,
            "min_quantity": format_quantity(product.min_quantity),
            "indications": product.indications,
            "note": product.note,
        }
        for key, value in values.items():
            self.fields[key].set(value)
        self.added_field.set(format_created(product.created_at))
        show_units(self.fields)

    def read_form(self) -> ProductForm:
        """Собирает введённые значения в форму для сервиса."""
        return read_form(self.fields)

    def _build_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setContentsMargins(-SHADOW_PAD, 0, -SHADOW_PAD, 0)
        grid.setHorizontalSpacing(COLUMN_GAP - 2 * SHADOW_PAD)
        grid.setVerticalSpacing(ROW_GAP - SHADOW_PAD - 2)
        for column in range(DIALOG_COLUMNS):
            grid.setColumnStretch(column, 1)
        order = [
            widget
            for key, widget in self.fields.items()
            if key not in ("note", "indications", "min_quantity", "storage_place")
        ]
        # Дата добавления стоит рядом со сроком годности.
        order.insert(list(self.fields).index("expiry_date") + 1, self.added_field)
        order += [
            self.fields["storage_place"],
            self.fields["min_quantity"],
            self.fields["indications"],
        ]
        for index, widget in enumerate(order):
            row, column = divmod(index, DIALOG_COLUMNS)
            grid.addWidget(widget, row, column, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(
            self.fields["note"],
            len(order) // DIALOG_COLUMNS,
            0,
            1,
            DIALOG_COLUMNS,
            Qt.AlignmentFlag.AlignTop,
        )
        return grid

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 0)
        row.setSpacing(4)
        row.addWidget(label("*", "label", "red"))
        row.addWidget(label(" — обязательные поля", "label", "ink_3"))
        row.addStretch(1)
        self.cancel_button = Button("Отмена", self._cancel)
        self.save_button = Button(
            "Сохранить изменения" if self.editing else "Сохранить",
            self._submit,
            variant="primary",
        )
        row.addWidget(self.cancel_button)
        row.addWidget(self.save_button)
        return row

    def _refresh_save(self) -> None:
        """Кнопка недоступна, пока у какого-нибудь поля показана ошибка."""
        self.save_button.set_enabled(not has_error(self.fields))

    def _cancel(self) -> None:
        self.close_modal()
        if self._on_cancel is not None:
            self._on_cancel()

    def on_cancel(self, callback: Callable[[], None]) -> None:
        """Вызывает функцию, когда окно закрыли без сохранения кнопкой «Отмена»."""
        self._on_cancel = callback

    def _submit(self) -> None:
        for widget in self.fields.values():
            widget.clear_error()
        products = self._services.products
        try:
            if self._product_id is None:
                view = products.add_product(self._user_id, self.read_form())
            else:
                view = products.update_product(
                    self._user_id, self._product_id, self.read_form()
                )
        except ValidationError as error:
            show_error(self.fields, error)
            self._refresh_save()
            return
        except NotFoundError:  # товар успели удалить
            self.close_modal()
            self._on_saved(None)
            return
        self.close_modal()
        self._on_saved(view)
