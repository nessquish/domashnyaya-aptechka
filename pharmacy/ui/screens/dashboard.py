"""Экран «Главная» (макет Figma, экран 03): сводка по аптечке."""

from datetime import date, datetime
from typing import TYPE_CHECKING, Callable, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy, QHBoxLayout, QVBoxLayout, QWidget

from pharmacy.ui.widgets.badge import Badge, badge_height, measure_badge
from pharmacy.ui.widgets.button import Button, measure_button
from pharmacy.ui.widgets.card import Card
from pharmacy.ui.widgets.common import Line, clickable, label, pad
from pharmacy.ui.widgets.iconbox import IconBox
from pharmacy.ui.widgets.link import Link
from pharmacy.ui.widgets.page import PageHeader
from pharmacy.services.dashboard_service import DashboardSummary
from pharmacy.services.product_service import ProductView
from pharmacy.services.status import ProductStatus
from pharmacy.ui import labels, sections
from pharmacy.ui.theme import CARD_SHADOW_PAD, SHADOW_PAD
from pharmacy.utils.dates import format_user_date
from pharmacy.utils.formatting import format_quantity

if TYPE_CHECKING:
    from pharmacy.ui.screens.shell import MainShell

STAT_GAP = 14 - 2 * CARD_SHADOW_PAD  # расстояние между карточками минус поля теней
COLUMN_GAP = 16 - 2 * CARD_SHADOW_PAD
LEFT_WEIGHT, RIGHT_WEIGHT = 1, 1  # две колонки одинаковой ширины
OPEN_TAB = 1  # вкладка «Не куплено» в списке покупок
ROW_PADDING_X = 18
ROW_PADDING_Y = 8
ICON_GAP = 12


def _detail(view: ProductView) -> str:
    """Вторая строка в списке «Требуют внимания»."""
    product = view.product
    status = view.primary_status
    if status is ProductStatus.EXPIRED:
        return f"Срок годности истёк {format_user_date(product.expiry_date)}"
    if status is ProductStatus.EXPIRING:
        return f"Годен до {format_user_date(product.expiry_date)}"
    unit = product.unit
    return (
        f"Осталось {format_quantity(product.quantity)} {unit}"
        f" · минимум {format_quantity(product.min_quantity)} {unit}"
    )


def _column() -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    return layout


def _row_layout() -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    return layout


class DashboardScreen(QWidget):
    """Приветствие, четыре счётчика, товары, требующие внимания, и новые товары."""

    def __init__(self, shell: "MainShell") -> None:
        super().__init__()
        self._shell = shell
        self._services = shell.services
        self._user = shell.user
        summary = self._services.dashboard.summary(self._user.id)
        self._button_width = max(
            measure_button("В список", "sm"),
            measure_button("В списке", "sm", "check"),
        )
        self._badge_width = max(measure_badge(s.label) for s in ProductStatus)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.stat_cards: List[Card] = []
        self._build_header()
        self._build_subtitle()
        self._build_stats(summary)
        self._build_columns(summary)
        self._layout.addStretch(1)

    # --- верхняя часть ---

    def _build_header(self) -> None:
        text = f"{labels.greeting(datetime.now().hour)}, {self._user.username}!"
        header = PageHeader(text)
        self.add_button = Button(
            "Добавить товар в аптечку",
            command=self._shell.add_product,
            variant="primary",
            icon="plus",
        )
        header.actions.addWidget(self.add_button)
        self._layout.addWidget(header)

    def _build_subtitle(self) -> None:
        today = format_user_date(date.today())
        subtitle = label(
            f"Вот краткая информация о ваших запасах на {today}", "lead", "ink_2"
        )
        pad(subtitle, CARD_SHADOW_PAD, 8, 0, 16)
        self._layout.addWidget(subtitle)

    def _build_stats(self, summary: DashboardSummary) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(STAT_GAP)
        shell = self._shell
        stats = (
            ("cross", "primary", summary.total, "Товаров в аптечке", shell.open_kit),
            (
                "alert",
                "amber",
                summary.attention_total,
                "Требуют внимания",
                lambda: shell.navigate(sections.NOTIFICATIONS),
            ),
            (
                "x",
                "red",
                summary.expired,
                "Просрочено",
                lambda: shell.open_kit(ProductStatus.EXPIRED),
            ),
            (
                "cart",
                "green",
                summary.shopping_open,
                "В списке покупок",
                lambda: shell.open_shopping(OPEN_TAB),
            ),
        )
        for icon, tone, value, caption, command in stats:
            card = Card()
            self._fill_stat(card, icon, tone, value, caption)
            clickable(card, command)
            row.addWidget(card, 1)
            self.stat_cards.append(card)
        self._layout.addLayout(row)

    def _fill_stat(
        self, card: Card, icon: str, tone: str, value: int, caption: str
    ) -> None:
        inset = card.inner_inset
        inner = _row_layout()
        inner.setContentsMargins(16 - inset, 14 - inset, 16 - inset, 14 - inset)
        inner.addWidget(IconBox(icon, tone))
        inner.addSpacing(ICON_GAP)
        texts = _column()
        texts.addWidget(label(str(value), "number", tight=True))
        texts.addWidget(label(caption, "small", "ink_2", tight=True))
        inner.addLayout(texts)
        inner.addStretch(1)
        card.body.addLayout(inner)

    # --- два списка ---

    def _build_columns(self, summary: DashboardSummary) -> None:
        columns = QHBoxLayout()
        columns.setContentsMargins(0, 16 - 2 * CARD_SHADOW_PAD, 0, 0)
        columns.setSpacing(COLUMN_GAP)
        self.attention_card = self._list_card(
            "Требуют внимания",
            "Все уведомления",
            lambda: self._shell.navigate(sections.NOTIFICATIONS),
        )
        self.recent_card = self._list_card(
            "Последние добавленные",
            "Вся аптечка",
            lambda: self._shell.navigate(sections.MY_KIT),
        )
        # Ширину колонок задают только веса: длинный текст не растягивает карточку.
        for card in (self.attention_card, self.recent_card):
            card.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        columns.addWidget(self.attention_card, LEFT_WEIGHT, Qt.AlignmentFlag.AlignTop)
        columns.addWidget(self.recent_card, RIGHT_WEIGHT, Qt.AlignmentFlag.AlignTop)
        self._fill_attention(self.attention_card, summary.attention)
        self._fill_recent(self.recent_card, summary.recent_products)
        self._layout.addLayout(columns)

    def _list_card(self, title: str, link: str, command: Callable[[], None]) -> Card:
        """Карточка со строкой заголовка и ссылкой справа."""
        card = Card()
        head = _row_layout()
        head.setContentsMargins(ROW_PADDING_X - card.inner_inset, 10, 0, 10)
        head.addWidget(label(title, "section"))
        head.addStretch(1)
        head.addWidget(Link(link, command, icon="arrow-right"))
        head.addSpacing(ROW_PADDING_X - card.inner_inset)
        card.body.addLayout(head)
        card.body.addWidget(Line())
        return card

    def _row(self, card: Card) -> QHBoxLayout:
        """Строка списка внутри карточки с отступами макета."""
        row = _row_layout()
        side = ROW_PADDING_X - card.inner_inset - SHADOW_PAD
        row.setContentsMargins(side, ROW_PADDING_Y, side, ROW_PADDING_Y)
        card.body.addLayout(row)
        return row

    @staticmethod
    def _empty(card: Card, text: str) -> None:
        message = label(text, "body", "ink_3")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pad(message, 0, 40, 0, 40)
        card.body.addWidget(message)

    def _fill_attention(self, card: Card, views: List[ProductView]) -> None:
        if not views:
            self._empty(card, "Всё в порядке: срочных дел нет")
            return
        for index, view in enumerate(views):
            if index:
                card.body.addWidget(Line())
            self._attention_row(card, view)

    def _attention_row(self, card: Card, view: ProductView) -> None:
        status = view.primary_status
        row = self._row(card)
        row.addSpacing(SHADOW_PAD)
        row.addWidget(
            IconBox(labels.STATUS_ICONS[status], labels.STATUS_TONES[status], "sm")
        )
        row.addSpacing(ICON_GAP)
        texts = _column()
        texts.addWidget(self._product_link(view), 0, Qt.AlignmentFlag.AlignLeft)
        texts.addWidget(label(_detail(view), "small", "ink_2", tight=True))
        row.addLayout(texts, 1)
        # Все кнопки и плашки в списке одной ширины и стоят в своих столбцах,
        # чтобы края не «плыли» от строки к строке.
        slot = QWidget()
        slot.setFixedSize(self._badge_width, badge_height())
        Badge(status.label, labels.STATUS_TONES[status], parent=slot)
        row.addWidget(slot)
        row.addSpacing(ICON_GAP)
        product_id = view.product.id
        if self._services.shopping.is_in_list(self._user.id, product_id):
            action = Button(
                "В списке", size="sm", icon="check", width=self._button_width
            )
            action.set_enabled(False)
        else:
            action = Button(
                "В список",
                size="sm",
                width=self._button_width,
                command=lambda: self._add_to_list(product_id),
            )
        row.addWidget(action)

    def _fill_recent(self, card: Card, views: List[ProductView]) -> None:
        if not views:
            self._empty(card, "Товаров пока нет")
            return
        for index, view in enumerate(views):
            if index:
                card.body.addWidget(Line())
            row = self._row(card)
            product = view.product
            added = format_user_date(
                datetime.strptime(product.created_at[:10], "%Y-%m-%d").date()
            )
            texts = _column()
            texts.setContentsMargins(SHADOW_PAD, 0, SHADOW_PAD, 0)
            texts.addWidget(self._product_link(view), 0, Qt.AlignmentFlag.AlignLeft)
            texts.addWidget(
                label(
                    f"{labels.short_category(product.category_name)} · {added}",
                    "small",
                    "ink_2",
                )
            )
            row.addLayout(texts, 1)

    def _product_link(self, view: ProductView) -> Link:
        """Название товара, по нажатию на которое открывается его карточка."""
        product_id = view.product.id
        return Link(
            view.product.name,
            lambda: self._shell.open_product(product_id),
            style="strong",
        )

    def _add_to_list(self, product_id: int) -> None:
        """Добавляет товар в список покупок и обновляет экран."""
        self._services.shopping.add_from_product(self._user.id, product_id)
        self._shell.navigate(sections.HOME)
