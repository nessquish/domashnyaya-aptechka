"""Экран «Моя аптечка» (макет Figma, экраны 04 и 15): таблица товаров."""

import math
from datetime import date
from typing import TYPE_CHECKING, List, Optional, Set

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from pharmacy.ui.widgets.actionbar import HEIGHT as BAR_HEIGHT, ActionBar
from pharmacy.ui.widgets.badge import Badge
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.controls import Checkbox
from pharmacy.ui.widgets.footer import fill_footer
from pharmacy.ui.widgets.dialog import Dialog
from pharmacy.ui.widgets.popup import PopupList
from pharmacy.ui.widgets.empty import EmptyState
from pharmacy.ui.widgets.field import TextField
from pharmacy.ui.widgets.page import ACTION_INSET, PageHeader
from pharmacy.ui.widgets.select import Select
from pharmacy.ui.widgets.sortselect import SortSelect
from pharmacy.ui.widgets.table import Column, DataTable, TextCell
from pharmacy.ui.widgets.wrap import TwoSideLayout
from pharmacy.models import ShoppingSource
from pharmacy.services.product_service import ProductView
from pharmacy.services.status import ProductStatus
from pharmacy.ui import labels, sorting
from pharmacy.ui.paging import DEFAULT_ROWS, fitted_rows, remembered_rows
from pharmacy.ui.theme import CARD_SHADOW_PAD, SHADOW_PAD
from pharmacy.utils.dates import format_user_date
from pharmacy.utils.formatting import format_quantity

if TYPE_CHECKING:
    from pharmacy.ui.screens.shell import MainShell

PAGE_SIZE = DEFAULT_ROWS  # строк на странице, пока окно не измерено
PAGING_KEY = "my_kit"
FLASH_MS = 4000  # сколько держится подсветка найденного товара
SEARCH_DELAY_MS = 250
SORT_PREFERENCE = "kit_sort"  # выбранная сортировка запоминается для пользователя
COLUMNS = (
    Column("Название", 20),
    Column("Дата добавления", 16),
    Column("Категория", 13),
    Column("Количество", 15),
    Column("Ед. изм.", 9),
    Column("Срок годности", 14),
    Column("Место хранения", 14),
    Column("Состояние", 17),
)


def _added(product) -> str:
    """Дата добавления товара в формате ДД.ММ.ГГГГ."""
    try:
        return format_user_date(date.fromisoformat(product.created_at[:10]))
    except ValueError:
        return "—"


class MyKitScreen(QWidget):
    """Список товаров с поиском, фильтрами, сортировкой и страницами."""

    def __init__(
        self,
        shell: "MainShell",
        status: Optional[ProductStatus] = None,
    ) -> None:
        """Создаёт экран.

        Args:
            shell: Оболочка главного окна.
            status: Фильтр по состоянию, выбранный с самого начала
                (например, «Просрочен» при переходе с главной).
        """
        super().__init__()
        self._shell = shell
        self._services = shell.services
        self._user = shell.user
        self._search = ""
        self._category: Optional[int] = None
        self._status = status
        saved = shell.app.preferences.get(
            self._user.id, SORT_PREFERENCE, sorting.DEFAULT_SORT
        )
        # Сортировка не выбрана или запомнено что-то неизвестное: по состоянию.
        self._sort = saved if sorting.is_sort(saved) else sorting.DEFAULT_SORT
        self._page = 1
        self._page_size = remembered_rows(PAGING_KEY)
        self._selected: Set[int] = set()  # отмеченные товары (на всех страницах)
        self._shown_ids: List[int] = []
        self._total = 0
        self._flash_id: Optional[int] = None  # найденная товарная строка
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DELAY_MS)
        self._search_timer.timeout.connect(self._apply_search)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._layout.addWidget(PageHeader("Моя аптечка"))
        if self._services.products.list_products(self._user.id):
            self._build_toolbar()
            self._build_table()
            self._reload()
        else:
            self._build_empty()
        self._layout.addStretch(1)

    # --- пустая аптечка (экран 15) ---

    def _build_empty(self) -> None:
        card = Card()
        card.body.addWidget(
            EmptyState(
                "В аптечке пока пусто",
                "Добавьте первое лекарство или бытовое средство,\n"
                "чтобы следить за сроками годности и остатками",
                "Добавить товар в аптечку",
                self._shell.add_product,
            )
        )
        wrapper = QVBoxLayout()
        wrapper.setContentsMargins(0, 18 - CARD_SHADOW_PAD, 0, 0)
        wrapper.addWidget(card)
        self._layout.addLayout(wrapper)

    # --- панель ---

    def _build_toolbar(self) -> None:
        toolbar = QWidget()
        wrap = TwoSideLayout(toolbar, align_right=False, gap=8 - 2 * SHADOW_PAD)
        wrap.setContentsMargins(
            ACTION_INSET, 18 - SHADOW_PAD, ACTION_INSET, 14 - SHADOW_PAD
        )
        # В узком окне поиск и фильтры переходят на вторую строку.
        rest = QWidget()
        bar = QHBoxLayout(rest)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(8 - 2 * SHADOW_PAD)
        self.add_button = Button(
            "Добавить товар в аптечку",
            command=self._shell.add_product,
            variant="primary",
            icon="plus",
        )
        wrap.addWidget(self.add_button)
        self._search_field = TextField(
            placeholder="Поиск по названию…",
            leading_icon="search",
            compact=True,
            on_change=self._on_search,
        )
        # Поиск занимает всё свободное место панели, поэтому при крупном тексте
        # фильтры не вылезают за край окна.
        bar.addWidget(self._search_field, 1)
        categories = [(None, "Все категории")] + [
            (c.id, c.name) for c in self._services.products.list_categories()
        ]
        self.category_select = Select(
            categories, None, compact=True, on_change=self._on_category
        )
        states = [(None, "Любое состояние")] + [(s, s.label) for s in ProductStatus]
        self.status_select = Select(
            states, self._status, compact=True, on_change=self._on_status
        )
        self.sort_select = SortSelect(self._sort, self._on_sort)
        for select in (self.category_select, self.status_select, self.sort_select):
            bar.addWidget(select, 0, Qt.AlignmentFlag.AlignTop)
        wrap.addWidget(rest)
        self._layout.addWidget(toolbar)

    def _on_search(self) -> None:
        """Ищет с задержкой, чтобы не перерисовывать таблицу на каждую букву."""
        self._search_timer.start()

    def _apply_search(self) -> None:
        self._search = self._search_field.get().strip()
        self._restart()

    def _restart(self) -> None:
        """Возвращает на первую страницу и перерисовывает таблицу."""
        self._page = 1
        self._reload()

    def _on_category(self, value: object) -> None:
        self._category = value
        self._restart()

    def _on_status(self, value: object) -> None:
        self._status = value
        self._restart()

    def _on_sort(self, value: object) -> None:
        """Выбран подвид сортировки: запоминаем его и перерисовываем таблицу."""
        self._sort = str(value)
        self._shell.app.preferences.set(self._user.id, SORT_PREFERENCE, self._sort)
        self._restart()

    def _on_header(self, kind: sorting.SortKind) -> None:
        """Нажатие на заголовок столбца.

        Если таблица отсортирована по этому столбцу, меняется подвид («от А до Я»
        на «от Я до А»), иначе включается сортировка по нему.
        """
        if sorting.kind_of(self._sort) is kind:
            value = sorting.toggled(self._sort)
        else:
            value = kind.choices[0].value
        self.sort_select.set(value)
        self._on_sort(value)

    @property
    def sort(self) -> str:
        """Значение выбранной сортировки (подвид, например ``name_desc``)."""
        return self._sort

    def _load(self) -> List[ProductView]:
        """Товары по текущим поиску, фильтрам и сортировке."""
        views = self._services.products.list_products(
            self._user.id,
            search=self._search,
            category_id=self._category,
            status=self._status,
            sort=self._sort,
        )
        if sorting.kind_of(self._sort).key == "category":
            # В таблице категории показаны короткими названиями («Мед. товары»),
            # поэтому и порядок считается по ним: он должен быть виден глазами.
            views.sort(
                key=lambda v: labels.short_category(v.product.category_name).casefold(),
                reverse=self._sort.endswith("_desc"),
            )
        return views

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.fit_rows)

    def fit_rows(self) -> None:
        """Подгоняет число строк на странице под высоту окна."""
        if not hasattr(self, "_card"):
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
            0 if self._bar.isVisible() else BAR_HEIGHT,
        )
        if size != self._page_size:
            first = (self._page - 1) * self._page_size
            self._page_size = size
            self._page = first // size + 1
            self._reload()
            QTimer.singleShot(0, self.fit_rows)

    def reveal(self, product_id: int) -> None:
        """Переходит на страницу таблицы, где стоит товар, и подсвечивает строку.

        Нужно после добавления товара и по результату поиска. Если поиск или
        фильтры прячут товар, они сбрасываются.
        """
        views = self._load()
        if all(view.product.id != product_id for view in views):
            self._reset_filters()
            views = self._load()
        for index, view in enumerate(views):
            if view.product.id == product_id:
                self._page = index // self._page_size + 1
                self._flash_id = product_id
                self._reload()
                QTimer.singleShot(FLASH_MS, self._clear_flash)
                return

    def _reset_filters(self) -> None:
        self._search = ""
        self._category = None
        self._status = None
        self._search_field.set("")
        self.category_select.set(None)
        self.status_select.set(None)

    def _clear_flash(self) -> None:
        """Снимает подсветку найденной строки (отмеченные флажком остаются)."""
        try:
            flashed, self._flash_id = self._flash_id, None
            if flashed in self._shown_ids and flashed not in self._selected:
                self._table.set_row_selected(self._shown_ids.index(flashed), False)
        except RuntimeError:  # экран уже закрыт
            pass

    # --- таблица ---

    def _build_table(self) -> None:
        card = Card(flush=True)
        self._card = card
        self._bar = ActionBar(card)
        self.clear_button = Button("Снять выбор", self._clear_selection, size="sm")
        self.all_button = Button("Выбрать все", self._select_everything, size="sm")
        self.category_button = Button(
            "Сменить категорию", self._open_category_list, size="sm"
        )
        self.shopping_button = Button(
            "В список покупок",
            self._add_to_shopping,
            variant="primary",
            size="sm",
            icon="plus",
        )
        self.delete_button = Button(
            "Удалить выбранные", self._confirm_delete, variant="danger", size="sm"
        )
        for button in (
            self.clear_button,
            self.all_button,
            self.category_button,
            self.shopping_button,
            self.delete_button,
        ):
            self._bar.buttons.addWidget(button)
        card.body.addWidget(self._bar)
        self._table = DataTable(COLUMNS, card, selectable=True)
        self._select_page = self._table.set_header_widget(
            -1, lambda: Checkbox(False, self._toggle_page)
        )
        for kind in sorting.SORT_KINDS:
            if kind.column is not None:
                self._table.set_header_click(
                    kind.column, lambda k=kind: self._on_header(k)
                )
        card.body.addWidget(self._table)
        self._footer = QVBoxLayout()
        self._footer.setContentsMargins(0, 0, 0, 0)
        self._footer.setSpacing(0)
        card.body.addLayout(self._footer)
        self._layout.addWidget(card)

    def _reload(self) -> None:
        """Заново читает товары по текущим условиям и перерисовывает таблицу."""
        views = self._load()
        size = self._page_size
        pages = max(math.ceil(len(views) / size), 1)
        self._page = min(self._page, pages)
        start = (self._page - 1) * size
        shown = views[start : start + size]
        self.setUpdatesEnabled(False)
        try:
            self._show_sort()
            self._table.clear()
            self._shown_ids = [view.product.id for view in shown]
            self._total = len(views)
            if not shown:
                self._table.add_message("Ничего не найдено")
            for view in shown:
                pid = view.product.id
                self._table.add_row(
                    self._cells(view),
                    pid in self._selected or pid == self._flash_id,
                    check=lambda i=pid: Checkbox(
                        i in self._selected, lambda v, i=i: self._toggle(i, v)
                    ),
                    on_click=lambda i=pid: self._flip(i),
                )
            self.summary, self.pagination = fill_footer(
                self._footer,
                self._page,
                pages,
                len(views),
                start,
                len(shown),
                self._on_page,
            )
            self._update_bar()
        finally:
            self.setUpdatesEnabled(True)

    # --- выбор строк и массовые действия ---

    @property
    def selected(self) -> Set[int]:
        """Номера отмеченных товаров."""
        return set(self._selected)

    @property
    def bar(self) -> ActionBar:
        """Панель действий над отмеченными товарами."""
        return self._bar

    @property
    def select_page(self) -> Checkbox:
        """Общий флажок в шапке: отметить товары страницы."""
        return self._select_page

    def _mark(self, product_ids: List[int], value: bool) -> None:
        """Ставит или снимает отметку у товаров."""
        if value:
            self._selected.update(product_ids)
        else:
            self._selected.difference_update(product_ids)

    def _toggle(self, product_id: int, value: bool) -> None:
        self._mark([product_id], value)
        if product_id in self._shown_ids:
            self._table.set_row_selected(self._shown_ids.index(product_id), value)
        self._update_bar()

    def _flip(self, product_id: int) -> None:
        """Нажатие на свободное место строки отмечает или снимает отметку."""
        self._toggle(product_id, product_id not in self._selected)
        for box, shown_id in zip(self._table.check_widgets(), self._shown_ids):
            box.set(shown_id in self._selected)

    def _toggle_page(self, value: bool) -> None:
        self._mark(self._shown_ids, value)
        self._reload()

    def _select_everything(self) -> None:
        """Отмечает все товары, подходящие под поиск и фильтры, на всех страницах."""
        self._selected |= {view.product.id for view in self._load()}
        self._reload()

    def _clear_selection(self) -> None:
        self._selected.clear()
        self._reload()

    def _update_bar(self) -> None:
        count = len(self._selected)
        self._table.set_rounded_top(not count)
        if count:
            self._bar.show_bar(f"Выбрано: {count}")
        else:
            self._bar.hide_bar()
        self.all_button.setVisible(count < self._total)
        self._select_page.set(
            bool(self._shown_ids) and self._selected.issuperset(self._shown_ids)
        )

    def _finish(self, message: str) -> None:
        """Снимает отметки и на пару секунд показывает итог действия в панели."""
        self._selected.clear()
        self._reload()
        self._bar.flash(message, self._update_bar)
        self._table.set_rounded_top(False)

    def _add_to_shopping(self) -> None:
        created, increased = self._services.shopping.add_products(
            self._user.id, sorted(self._selected), ShoppingSource.KIT
        )
        parts = []
        if created:
            parts.append(f"добавлено в список покупок: {created}")
        if increased:
            parts.append(f"увеличено количество: {increased}")
        self._finish((", ".join(parts) or "Ничего не добавлено").capitalize())

    def _confirm_delete(self) -> None:
        Dialog(
            self._shell.app,
            "Удалить выбранные товары?",
            f"Товаров к удалению: {len(self._selected)}. "
            "Это действие нельзя отменить.",
            "Удалить",
            self._delete_selected,
            confirm_variant="danger_solid",
            warning=True,
        )

    def _delete_selected(self) -> None:
        deleted = self._services.products.delete_products(
            self._user.id, sorted(self._selected)
        )
        self._shell.refresh_counters()
        self._finish(f"Удалено товаров: {deleted}")

    def _open_category_list(self) -> None:
        options = [(c.id, c.name) for c in self._services.products.list_categories()]
        PopupList(self.category_button, options, None, self._change_category)

    def _change_category(self, category_id: object) -> None:
        changed = self._services.products.change_category(
            self._user.id, sorted(self._selected), int(category_id)
        )
        self._finish(f"Категория изменена у товаров: {changed}")

    def _show_sort(self) -> None:
        """Подпись сортировки (фиолетовая) только рядом с выбранным столбцом."""
        self._update_quantity_range()
        kind = sorting.kind_of(self._sort)
        self._table.set_sort_caption(kind.column, sorting.caption_of(self._sort))
        for other in sorting.SORT_KINDS:
            if other.column is None:
                continue
            if other is kind:
                tip = (
                    f"Сортировка: {sorting.label_of(self._sort)}. "
                    "Нажмите, чтобы поменять: "
                    f"{sorting.label_of(sorting.toggled(self._sort))}"
                )
            else:
                tip = f"Нажмите, чтобы отсортировать {other.label.lower()}"
            self._table.set_header_tip(other.column, tip)

    def _update_quantity_range(self) -> None:
        """Берёт наименьшее и наибольшее количество из всей аптечки для подписей."""
        quantities = [
            view.product.quantity
            for view in self._services.products.list_products(self._user.id)
        ]
        sorting.set_quantity_range(
            min(quantities, default=None), max(quantities, default=None)
        )

    @property
    def table(self) -> DataTable:
        """Таблица товаров."""
        return self._table

    def _cells(self, view: ProductView) -> List:
        product = view.product
        status = view.primary_status
        expiry = (
            TextCell(format_user_date(product.expiry_date), "ink_2")
            if product.expiry_date
            else TextCell("—", "ink_3")
        )
        return [
            TextCell(
                product.name,
                "primary",
                bold=True,
                on_click=lambda p=product.id: self._shell.open_product(p),
            ),
            TextCell(_added(product), "ink_2"),
            TextCell(labels.short_category(product.category_name), "ink_2"),
            TextCell(format_quantity(product.quantity), "ink_2"),
            TextCell(product.unit, "ink_2"),
            expiry,
            TextCell(product.storage_place or "—", "ink_2"),
            lambda: Badge(status.label, labels.STATUS_TONES[status]),
        ]

    def _on_page(self, page: int) -> None:
        self._page = page
        self._reload()
