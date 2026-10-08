"""Экран «Моя аптечка» (макет Figma, экраны 04 и 15): таблица товаров."""

import math
from typing import TYPE_CHECKING, List, Optional, Set

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from pharmacy.ui.widgets.actionbar import HEIGHT as BAR_HEIGHT, ActionBar
from pharmacy.ui.widgets.badge import Badge
from pharmacy.ui.widgets.button import Button
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.common import Line, clear_layout, label
from pharmacy.ui.widgets.controls import Checkbox, Pagination
from pharmacy.ui.widgets.dialog import Dialog
from pharmacy.ui.widgets.popup import PopupList
from pharmacy.ui.widgets.empty import EmptyState
from pharmacy.ui.widgets.field import TextField
from pharmacy.ui.widgets.page import ACTION_INSET, PageHeader
from pharmacy.ui.widgets.select import Select
from pharmacy.ui.widgets.sortselect import SortSelect
from pharmacy.ui.widgets.table import Column, DataTable, TextCell
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
SEARCH_DELAY_MS = 250
SORT_PREFERENCE = "kit_sort"  # выбранная сортировка запоминается для пользователя
COLUMNS = (
    Column("Название", 30),
    Column("Категория", 20),
    Column("Количество", 14),
    Column("Ед. изм.", 11),
    Column("Срок годности", 17),
    Column("Место хранения", 17),
    Column("Состояние", 18),
)


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
        bar = QHBoxLayout()
        bar.setContentsMargins(
            ACTION_INSET, 18 - SHADOW_PAD, ACTION_INSET, 14 - SHADOW_PAD
        )
        bar.setSpacing(8 - 2 * SHADOW_PAD)
        self.add_button = Button(
            "Добавить товар в аптечку",
            command=self._shell.add_product,
            variant="primary",
            icon="plus",
        )
        bar.addWidget(self.add_button)
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
        self._layout.addLayout(bar)

    def _on_search(self) -> None:
        """Ищет с задержкой, чтобы не перерисовывать таблицу на каждую букву."""
        self._search_timer.start()

    def _apply_search(self) -> None:
        self._search = self._search_field.get().strip()
        self._page = 1
        self._reload()

    def _on_category(self, value: object) -> None:
        self._category = value
        self._page = 1
        self._reload()

    def _on_status(self, value: object) -> None:
        self._status = value
        self._page = 1
        self._reload()

    def _on_sort(self, value: object) -> None:
        """Выбран подвид сортировки: запоминаем его и перерисовываем таблицу."""
        self._sort = str(value)
        self._shell.app.preferences.set(self._user.id, SORT_PREFERENCE, self._sort)
        self._page = 1
        self._reload()

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
        """Переходит на страницу таблицы, где стоит товар (после добавления)."""
        views = self._load()
        for index, view in enumerate(views):
            if view.product.id == product_id:
                self._page = index // self._page_size + 1
                self._reload()
                return

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
                    pid in self._selected,
                    check=lambda i=pid: Checkbox(
                        i in self._selected, lambda v, i=i: self._toggle(i, v)
                    ),
                    on_click=lambda i=pid: self._flip(i),
                )
            self._build_footer(len(views), start, len(shown), pages)
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

    def _toggle(self, product_id: int, value: bool) -> None:
        if value:
            self._selected.add(product_id)
        else:
            self._selected.discard(product_id)
        if product_id in self._shown_ids:
            self._table.set_row_selected(self._shown_ids.index(product_id), value)
        self._update_bar()

    def _flip(self, product_id: int) -> None:
        """Нажатие на свободное место строки отмечает или снимает отметку."""
        self._toggle(product_id, product_id not in self._selected)
        for box, shown_id in zip(self._table.check_widgets(), self._shown_ids):
            box.set(shown_id in self._selected)

    def _toggle_page(self, value: bool) -> None:
        for product_id in self._shown_ids:
            if value:
                self._selected.add(product_id)
            else:
                self._selected.discard(product_id)
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
        everything = bool(self._shown_ids) and all(
            i in self._selected for i in self._shown_ids
        )
        self._select_page.set(everything)

    def _finish(self, message: str) -> None:
        """Снимает отметки и на пару секунд показывает итог действия в панели."""
        self._selected.clear()
        self._reload()
        self._bar.flash(message, self._update_bar)
        self._table.set_rounded_top(False)

    def _add_to_shopping(self) -> None:
        added, skipped = self._services.shopping.add_products(
            self._user.id, sorted(self._selected)
        )
        text = f"Добавлено в список покупок: {added}"
        if skipped:
            text += f" (уже в списке: {skipped})"
        self._finish(text)

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
        kind = sorting.kind_of(self._sort)
        choice = sorting.choice_of(self._sort)
        self._table.set_sort_caption(kind.column, choice.caption)
        for other in sorting.SORT_KINDS:
            if other.column is None:
                continue
            if other is kind:
                tip = (
                    f"Сортировка: {choice.label}. Нажмите, чтобы поменять: "
                    f"{sorting.choice_of(sorting.toggled(self._sort)).label}"
                )
            else:
                tip = f"Нажмите, чтобы отсортировать {other.label.lower()}"
            self._table.set_header_tip(other.column, tip)

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
            TextCell(labels.short_category(product.category_name), "ink_2"),
            TextCell(format_quantity(product.quantity), "ink_2"),
            TextCell(product.unit, "ink_2"),
            expiry,
            TextCell(product.storage_place or "—", "ink_2"),
            lambda: Badge(status.label, labels.STATUS_TONES[status]),
        ]

    def _build_footer(self, total: int, start: int, shown: int, pages: int) -> None:
        clear_layout(self._footer)
        self._footer.addWidget(Line("line"))
        row = QHBoxLayout()
        row.setContentsMargins(14, 10, 14, 10)
        text = (
            f"Показано {start + 1}–{start + shown} из {total}"
            if shown
            else "Показано 0 из 0"
        )
        self.summary = label(text, "small", "ink_2")
        row.addWidget(self.summary)
        row.addStretch(1)
        self.pagination = Pagination(self._page, pages, self._on_page)
        row.addWidget(self.pagination)
        self._footer.addLayout(row)

    def _on_page(self, page: int) -> None:
        self._page = page
        self._reload()
