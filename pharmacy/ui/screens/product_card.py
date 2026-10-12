"""Карточка товара (макет Figma, экраны 06 и 08): окно поверх текущего экрана."""

from datetime import datetime
from typing import TYPE_CHECKING, List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from pharmacy.models import ShoppingSource
from pharmacy.errors import NotFoundError, ValidationError
from pharmacy.services.product_service import ProductView
from pharmacy.services.status import ProductStatus
from pharmacy.ui import labels
from pharmacy.ui.theme import SHADOW_PAD
from pharmacy.ui.widgets.badge import Badge
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.common import Line, label, pad
from pharmacy.ui.widgets.dialog import Dialog, Modal
from pharmacy.ui.widgets.iconbox import IconBox
from pharmacy.ui.widgets.iconbutton import IconButton
from pharmacy.utils.dates import format_user_date
from pharmacy.utils.formatting import format_quantity, plural

if TYPE_CHECKING:
    from pharmacy.ui.screens.shell import MainShell

DIALOG_WIDTH = 680
COLUMN_GAP = 30
NO_DATA = "Нет данных"
DISCLAIMER = "Показания вносятся пользователем и не являются медицинской рекомендацией."
DELETE_TEXT = (
    "Товар будет удалён из аптечки вместе со связанными уведомлениями. "
    "Записи в истории останутся. Действие нельзя отменить."
)
WIDE_FIELDS = {"Показания / назначение", "Примечание"}


def _days_phrase(days: int) -> str:
    """Подпись рядом со сроком: «через 19 дней» или «просрочено на 3 дня»."""
    if days < 0:
        count = -days
        return f"просрочено на {count} {plural(count, 'день', 'дня', 'дней')}"
    if days == 0:
        return "истекает сегодня"
    return f"через {days} {plural(days, 'день', 'дня', 'дней')}"


class ProductCardDialog(Modal):
    """Подробные данные о товаре и действия над ним: окно поверх текущего экрана.

    Attributes:
        view: Показанный товар с его состояниями.
    """

    def __init__(self, shell: "MainShell", product_id: int) -> None:
        """Открывает карточку.

        Args:
            shell: Оболочка главного окна.
            product_id: Товар, который показываем.

        Raises:
            NotFoundError: Если такого товара нет.
        """
        view = shell.services.products.get_product(shell.user.id, product_id)
        super().__init__(shell.app, DIALOG_WIDTH)
        self._shell = shell
        self._services = shell.services
        self._user = shell.user
        self._product_id = product_id
        self.view: ProductView = view
        self.body.addLayout(self._build_head())
        self.body.addSpacing(14)
        self.body.addWidget(Line("line"))
        self.body.addWidget(self._build_details())
        self.body.addWidget(Line("line"))
        self.body.addLayout(self._build_actions())
        note = label(DISCLAIMER, "label", "ink_3")
        pad(note, 0, 10, 0, 0)
        self.body.addWidget(note)

    # --- построение ---

    def _build_head(self) -> QHBoxLayout:
        product = self.view.product
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addWidget(IconBox("cross", "primary"))
        row.addSpacing(12)
        names = QVBoxLayout()
        names.setContentsMargins(0, 0, 0, 0)
        names.setSpacing(0)
        self.title = label(product.name, "product_title", tight=True)
        names.addWidget(self.title)
        added = datetime.strptime(product.created_at[:10], "%Y-%m-%d").date()
        names.addSpacing(2)
        names.addWidget(
            label(
                f"{product.category_name} · добавлен {format_user_date(added)}",
                "small",
                "ink_3",
                tight=True,
            )
        )
        row.addLayout(names)
        row.addStretch(1)
        for status in self.view.statuses:
            row.addSpacing(6)
            row.addWidget(Badge(status.label, labels.STATUS_TONES[status]))
        row.addSpacing(10)
        self.close_button = IconButton("x", self.close_modal)
        row.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        return row

    def _details(self) -> List[Tuple[str, str, str]]:
        """Пары «название поля, значение, цвет значения» для таблицы данных."""
        product = self.view.product
        unit = product.unit
        expiry = NO_DATA
        if product.expiry_date is not None:
            expiry = format_user_date(product.expiry_date)
        return [
            ("Количество", f"{format_quantity(product.quantity)} {unit}", "ink"),
            (
                "Минимальный остаток",
                f"{format_quantity(product.min_quantity)} {unit}",
                "ink",
            ),
            ("Срок годности", expiry, "ink" if product.expiry_date else "ink_3"),
            ("Место хранения", product.storage_place or NO_DATA, "ink"),
            ("Показания / назначение", product.indications or NO_DATA, "ink"),
            ("Примечание", product.note or NO_DATA, "ink"),
        ]

    def _build_details(self) -> QWidget:
        host = QWidget()
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 2, 0, 2)
        grid.setSpacing(0)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        row = column = 0
        for title, value, color in self._details():
            cell = self._detail_cell(title, value, color)
            if title in WIDE_FIELDS:
                if column:
                    row, column = row + 1, 0
                grid.addWidget(cell, row, 0, 1, 2)
                row += 1
            else:
                if column == 0:
                    cell.layout().setContentsMargins(0, 0, COLUMN_GAP, 0)
                grid.addWidget(cell, row, column)
                column += 1
                if column == 2:
                    row, column = row + 1, 0
        return host

    def _detail_cell(self, title: str, value: str, color: str) -> QWidget:
        cell = QWidget()
        outer = QVBoxLayout(cell)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        inner = QVBoxLayout()
        inner.setContentsMargins(0, 11, 0, 11)
        inner.setSpacing(0)
        inner.addWidget(label(title, "label", "ink_3", tight=True))
        inner.addSpacing(4)
        line = QHBoxLayout()
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(0)
        line.addWidget(
            label(value, "value", color, wrap=title in WIDE_FIELDS, tight=True)
        )
        if title == "Срок годности" and self.view.days_left is not None:
            tone = "red" if self.view.days_left < 0 else "amber"
            if ProductStatus.EXPIRED not in self.view.statuses and (
                ProductStatus.EXPIRING not in self.view.statuses
            ):
                tone = "ink_3"
            line.addWidget(
                label(
                    f" · {_days_phrase(self.view.days_left)}", "small", tone, tight=True
                )
            )
        line.addStretch(1)
        inner.addLayout(line)
        outer.addLayout(inner)
        outer.addWidget(Line("line_soft"))
        return cell

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        # Кнопки шире своей видимой части на поле под тень: выравниваем по тексту.
        row.setContentsMargins(-SHADOW_PAD, 10, -SHADOW_PAD, 0)
        row.setSpacing(0)
        self.delete_button = Button(
            "Удалить", command=self._confirm_delete, variant="danger"
        )
        row.addWidget(self.delete_button)
        row.addStretch(1)
        # Нажатие добавляет ещё одну единицу: количество в списке покупок растёт.
        in_list = self._services.shopping.is_in_list(self._user.id, self._product_id)
        self.list_button = Button(
            "Добавить ещё в список" if in_list else "В список покупок",
            command=self._add_to_list,
        )
        row.addWidget(self.list_button)
        self.edit_button = Button(
            "Редактировать", command=self._edit, variant="primary"
        )
        row.addWidget(self.edit_button)
        return row

    # --- действия ---

    def _add_to_list(self) -> None:
        try:
            self._services.shopping.add_from_product(
                self._user.id, self._product_id, source=ShoppingSource.CARD
            )
        except (NotFoundError, ValidationError):
            pass
        self.close_modal()
        self._shell.refresh()
        self._shell.open_product(self._product_id)

    def _edit(self) -> None:
        self.close_modal()
        self._shell.edit_product(self._product_id)

    def _confirm_delete(self) -> None:
        Dialog(
            self._shell.app,
            f"Удалить товар «{self.view.product.name}»?",
            DELETE_TEXT,
            "Удалить",
            self._delete,
            confirm_variant="danger_solid",
            warning=True,
        )

    def _delete(self) -> None:
        try:
            self._services.products.delete_product(self._user.id, self._product_id)
        except NotFoundError:
            pass
        self.close_modal()
        self._shell.refresh()
