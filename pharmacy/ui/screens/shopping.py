"""Экран «Список покупок» (макет Figma, экраны 09 и 10)."""

import math
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional, Set, Tuple

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from pharmacy.errors import ValidationError
from pharmacy.models import ShoppingItem, ShoppingSource
from pharmacy.ui.widgets.actionbar import ActionBar
from pharmacy.ui.widgets.badge import Badge
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.combo import ComboField
from pharmacy.ui.widgets.common import Line, clear_layout, label
from pharmacy.ui.widgets.controls import Checkbox, Pagination, Segmented
from pharmacy.ui.widgets.dialog import Modal
from pharmacy.ui.widgets.field import TextField
from pharmacy.ui.widgets.page import PageHeader
from pharmacy.ui.widgets.popup import PopupList
from pharmacy.ui.widgets.select import Select
from pharmacy.ui.widgets.table import Column, DataTable, TextCell
from pharmacy.ui.paging import fitted_rows, remembered_rows
from pharmacy.ui.theme import CARD_SHADOW_PAD, SHADOW_PAD
from pharmacy.utils.dates import format_user_date
from pharmacy.utils.formatting import format_quantity
from pharmacy.utils.units import DEFAULT_UNIT, UNITS

if TYPE_CHECKING:
    from pharmacy.ui.screens.shell import MainShell

FILTERS = (None, False, True)  # все, не куплено, куплено
SOURCE_LABELS = {
    ShoppingSource.NOTIFICATION: "Уведомление",
    ShoppingSource.MANUAL: "Вручную",
}
COLUMNS = (
    Column("", fixed=44),
    Column("Товар", 28),
    Column("Количество", 16),
    Column("Источник", 16),
    Column("Статус", 16),
    Column("Дата добавления", 20),
)
EMPTY_TEXT = "Список покупок пуст. Добавьте товар вручную или из уведомления."
DIALOG_WIDTH = 440
PAGING_KEY = "shopping"


def _created(item: ShoppingItem) -> str:
    """Дата добавления позиции в формате ДД.ММ.ГГГГ."""
    return format_user_date(datetime.strptime(item.created_at[:10], "%Y-%m-%d").date())


def _caption(product) -> str:
    """Строка подсказки: название и сколько этого товара сейчас в аптечке."""
    return f"{product.name} · {format_quantity(product.quantity)} {product.unit}"


class ShoppingScreen(QWidget):
    """Таблица позиций с фильтрами-вкладками, выбором строк и действиями над ними."""

    def __init__(self, shell: "MainShell", tab: int = 0) -> None:
        """Создаёт экран.

        Args:
            shell: Оболочка главного окна.
            tab: Выбранная вкладка: 0 все, 1 не куплено, 2 куплено.
        """
        super().__init__()
        self._shell = shell
        self._services = shell.services
        self._user = shell.user
        self._filter = tab
        self._selected: Set[int] = set()
        self._visible: List[ShoppingItem] = []  # позиции текущей страницы
        self._page = 1
        self._page_size = remembered_rows(PAGING_KEY)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        header = PageHeader("Список покупок")
        self._tabs = Segmented(self._tab_labels(), self._filter, self._on_tab)
        header.actions.addWidget(self._tabs)
        header.actions.addSpacing(10)
        self.add_button = Button(
            "Добавить вручную",
            command=self._open_add_dialog,
            variant="primary",
            icon="plus",
        )
        header.actions.addWidget(self.add_button)
        self._layout.addWidget(header)
        self._layout.addSpacing(18 - CARD_SHADOW_PAD - SHADOW_PAD)
        self._build_table()
        self._layout.addStretch(1)
        self._reload()

    # --- построение ---

    def _build_table(self) -> None:
        card = Card(flush=True)
        self._card = card
        self._bar = ActionBar(card)
        self.bought_button = Button(
            "Отметить как купленные",
            command=self._mark_bought,
            variant="primary",
            size="sm",
            icon="check",
        )
        self.remove_button = Button(
            "Удалить из списка",
            command=self._remove_selected,
            variant="danger",
            size="sm",
        )
        self._bar.buttons.addWidget(self.bought_button)
        self._bar.buttons.addWidget(self.remove_button)
        card.body.addWidget(self._bar)
        self._table = DataTable(COLUMNS, card)
        card.body.addWidget(self._table)
        self._select_all = self._table.set_header_widget(
            0, lambda: Checkbox(False, self._toggle_all)
        )
        self._footer = QVBoxLayout()
        self._footer.setContentsMargins(0, 0, 0, 0)
        self._footer.setSpacing(0)
        card.body.addLayout(self._footer)
        self._layout.addWidget(card)

    def _tab_labels(self) -> List[str]:
        items = self._services.shopping.list_items(self._user.id)
        bought = sum(1 for item in items if item.is_bought)
        return [
            f"Все · {len(items)}",
            f"Не куплено · {len(items) - bought}",
            f"Куплено · {bought}",
        ]

    # --- данные ---

    @property
    def table(self) -> DataTable:
        """Таблица позиций."""
        return self._table

    @property
    def tabs(self) -> Segmented:
        """Вкладки-фильтры."""
        return self._tabs

    @property
    def bar(self) -> ActionBar:
        """Панель действий над выбранными строками."""
        return self._bar

    @property
    def select_all(self) -> Checkbox:
        """Общий флажок в шапке таблицы."""
        return self._select_all

    @property
    def selected(self) -> Set[int]:
        """Номера выбранных позиций."""
        return set(self._selected)

    def _reload(self) -> None:
        """Заново читает список и перерисовывает вкладки, панель и таблицу."""
        found = self._services.shopping.list_items(self._user.id, FILTERS[self._filter])
        self._selected &= {item.id for item in found}
        size = self._page_size
        pages = max(math.ceil(len(found) / size), 1)
        self._page = min(self._page, pages)
        start = (self._page - 1) * size
        self._visible = found[start : start + size]
        self.setUpdatesEnabled(False)
        try:
            self._tabs.set_items(self._tab_labels())
            self._table.clear()
            if not self._visible:
                self._table.add_message(EMPTY_TEXT)
            for item in self._visible:
                self._table.add_row(self._cells(item), item.id in self._selected)
            self._build_footer(len(found), start, pages)
            self._update_bar()
        finally:
            self.setUpdatesEnabled(True)

    def _cells(self, item: ShoppingItem) -> List:
        bought = item.is_bought
        muted = "ink_3" if bought else "ink_2"
        linked = item.product_id is not None and not bought
        name = TextCell(
            item.name,
            "ink_3" if bought else ("primary" if linked else "ink"),
            bold=True,
            strike=bought,
            on_click=(
                (lambda p=item.product_id: self._shell.open_product(p))
                if linked
                else None
            ),
        )
        return [
            lambda: Checkbox(
                item.id in self._selected,
                lambda value, i=item.id: self._toggle(i, value),
            ),
            name,
            TextCell(f"{format_quantity(item.quantity)} {item.unit}", muted),
            TextCell(SOURCE_LABELS[item.source], muted),
            lambda: Badge(
                "Куплено" if bought else "Не куплено",
                "green" if bought else "red",
            ),
            TextCell(_created(item), muted),
        ]

    def _build_footer(self, total: int, start: int, pages: int) -> None:
        """Строка «Показано …» и переключатель страниц."""
        clear_layout(self._footer)
        if pages <= 1:
            return
        self._footer.addWidget(Line("line"))
        row = QHBoxLayout()
        row.setContentsMargins(14, 10, 14, 10)
        shown = len(self._visible)
        self.summary = label(
            f"Показано {start + 1}–{start + shown} из {total}", "small", "ink_2"
        )
        row.addWidget(self.summary)
        row.addStretch(1)
        self.pagination = Pagination(self._page, pages, self._on_page)
        row.addWidget(self.pagination)
        self._footer.addLayout(row)

    def _on_page(self, page: int) -> None:
        self._page = page
        self._reload()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.fit_rows)

    def fit_rows(self) -> None:
        """Подгоняет число строк на странице под высоту окна."""
        if not hasattr(self, "_footer"):
            return
        size = fitted_rows(
            PAGING_KEY,
            self,
            self._card,
            self._table,
            self._table.header_height,
            self._table.row_count,
            self._page_size,
            self._shell.viewport_height(),
        )
        if size != self._page_size:
            first = (self._page - 1) * self._page_size
            self._page_size = size
            self._page = first // size + 1
            self._reload()
            QTimer.singleShot(0, self.fit_rows)

    def _update_bar(self) -> None:
        """Показывает панель действий, пока выбрана хотя бы одна строка."""
        count = len(self._selected)
        # Сначала шапка таблицы отдаёт верхнюю полосу карточки, потом панель
        # занимает её (или шапка забирает обратно, когда панель скрыта).
        self._table.set_rounded_top(not count)
        if count:
            self._bar.show_bar(f"Выбрано: {count}")
        else:
            self._bar.hide_bar()
        everything = bool(self._visible) and count == len(self._visible)
        self._select_all.set(everything)

    # --- события ---

    def _on_tab(self, index: int) -> None:
        self._filter = index
        self._page = 1
        self._selected.clear()
        self._reload()

    def _toggle(self, item_id: int, value: bool) -> None:
        if value:
            self._selected.add(item_id)
        else:
            self._selected.discard(item_id)
        self._reload()

    def _toggle_all(self, value: bool) -> None:
        self._selected = {item.id for item in self._visible} if value else set()
        self._reload()

    def _mark_bought(self) -> None:
        for item_id in sorted(self._selected):
            self._services.shopping.set_bought(self._user.id, item_id, True)
        self._selected.clear()
        self._reload()

    def _remove_selected(self) -> None:
        for item_id in sorted(self._selected):
            self._services.shopping.remove(self._user.id, item_id)
        self._selected.clear()
        self._reload()

    def _open_add_dialog(self) -> None:
        AddItemDialog(self._shell.app, self._services, self._user.id, self._reload)


class ProductSearchField(ComboField):
    """Поле названия с подсказками: при вводе показывает подходящие товары аптечки.

    Список обновляется с каждой буквой. Выбранный товар запоминается, и позиция
    списка покупок получает ссылку на его карточку.
    """

    def __init__(self, products: List[Tuple[int, str, str]], *args, **kwargs) -> None:
        """Создаёт поле.

        Args:
            products: Товары аптечки: (номер, название, подпись в списке).
        """
        super().__init__([name for _, name, _ in products], *args, **kwargs)
        self._products = products
        self._picked: Optional[Tuple[int, str]] = None

    @property
    def product_id(self) -> Optional[int]:
        """Выбранный товар, если название не меняли после выбора."""
        if self._picked is not None and self._picked[1] == self.get().strip():
            return self._picked[0]
        return None

    def _matches(self, text: str) -> List[Tuple[object, str]]:
        needle = text.strip().casefold()
        return [
            (number, caption)
            for number, name, caption in self._products
            if needle and needle in name.casefold()
        ]

    def toggle_list(self) -> None:
        """Стрелка открывает все товары аптечки."""
        if self._popup is not None:
            self._popup.close_list()
            return
        if not self._products:
            return
        options = [(number, caption) for number, _, caption in self._products]
        self._popup = PopupList(
            self.frame,
            options,
            self.product_id,
            self._pick,
            self._closed,
            self.frame.box_rect(),
        )

    def _pick(self, value: object) -> None:
        if isinstance(value, int):
            name = next((n for number, n, _ in self._products if number == value), "")
            self._picked = (value, name)
            self.set(name)
            self.clear_error()
            if self._on_change is not None:
                self._on_change()
            return
        super()._pick(value)

    def _on_edited(self, text: str) -> None:
        super()._on_edited(text)
        self._refresh_suggestions()

    def _refresh_suggestions(self) -> None:
        """Обновляет список подсказок под введённым текстом."""
        options = self._matches(self.get())
        if not options or self.product_id is not None:
            if self._popup is not None:
                self._popup.close_list()
            return
        if self._popup is None:
            self._popup = PopupList(
                self.frame,
                options,
                None,
                self._pick,
                self._closed,
                self.frame.box_rect(),
                take_focus=False,
            )
        else:
            self._popup.replace_options(options, None, self._pick)


class AddItemDialog(Modal):
    """Окно «Добавить в список покупок»: название, количество и единица."""

    def __init__(self, host: QWidget, services, user_id: int, on_added) -> None:
        """Открывает окно.

        Args:
            host: Окно приложения.
            services: Сервисы приложения.
            user_id: Владелец списка.
            on_added: Вызывается после добавления позиции.
        """
        super().__init__(host, DIALOG_WIDTH, on_enter=self._submit)
        self._services = services
        self._user_id = user_id
        self._on_added = on_added
        self.add_title("Добавить в список покупок")
        self.add_text(
            "Начните вводить название: ниже появятся товары из аптечки", bottom=16
        )
        products = [
            (v.product.id, v.product.name, _caption(v.product))
            for v in services.products.list_products(user_id)
        ]
        self.name = ProductSearchField(
            products, "Название товара", "Введите название", required=True
        )
        self.body.addWidget(self.name)
        self.body.addSpacing(8)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        self.quantity = TextField("Количество", required=True)
        self.quantity.set("1")
        self.unit = Select(UNITS, DEFAULT_UNIT, label_text="Единица измерения")
        row.addWidget(self.quantity, 1)
        row.addWidget(self.unit, 1)
        self.body.addLayout(row)
        buttons = self.footer()
        self.cancel_button = Button("Отмена", self.close_modal)
        self.add_button = Button("Добавить", self._submit, variant="primary")
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.add_button)
        self.name.focus_field()

    def _submit(self) -> None:
        for field in (self.name, self.quantity, self.unit):
            field.clear_error()
        try:
            self._services.shopping.add_manual(
                self._user_id,
                self.name.get(),
                self.quantity.get(),
                self.unit.get() or DEFAULT_UNIT,
                self.name.product_id,
            )
        except ValidationError as error:
            target = {"name": self.name, "quantity": self.quantity}.get(
                error.field or ""
            )
            if target is not None:
                target.set_error(error.message)
            return
        self.close_modal()
        self._on_added()
