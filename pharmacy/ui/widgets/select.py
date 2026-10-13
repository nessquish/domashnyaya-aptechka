"""Выпадающий список: поле, по нажатию на которое открывается список вариантов."""

from typing import Callable, Optional, Sequence, Tuple, Union

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from pharmacy.ui.fonts import font, text_width
from pharmacy.ui.icons import icon_pixmap
from pharmacy.ui.paint import qcolor
from pharmacy.ui.widgets.field import (
    ICON_INSET,
    ICON_SIZE,
    TEXT_INSET,
    LabeledBox,
)
from pharmacy.ui.widgets.popup import Option, PopupList, Stage
from pharmacy.ui.theme import palette

OptionLike = Union[str, Option]
COMPACT_TEXT_INSET = 12
COMPACT_ARROW_GAP = 8  # расстояние между текстом и стрелкой в фильтре


def normalize(options: Sequence[OptionLike]) -> list:
    """Приводит варианты к виду (значение, подпись)."""
    return [(item, item) if isinstance(item, str) else tuple(item) for item in options]


class Select(LabeledBox):
    """Поле выбора из списка.

    Хранит значение выбранного варианта, а не его подпись: например,
    для категории это идентификатор.
    """

    def __init__(
        self,
        options: Sequence[OptionLike],
        value: object = None,
        label_text: Optional[str] = None,
        required: bool = False,
        placeholder: str = "",
        compact: bool = False,
        prefix: str = "",
        width: Optional[int] = None,
        on_change: Optional[Callable[[object], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Создаёт поле выбора.

        Args:
            options: Варианты: подписи или пары (значение, подпись).
            value: Выбранное значение (по умолчанию ничего не выбрано).
            label_text: Подпись над полем.
            required: Добавить красную звёздочку к подписи.
            placeholder: Серый текст, пока ничего не выбрано.
            compact: Вид фильтра на панели: граница цвета карточек, ширина по тексту.
            prefix: Слова перед значением («Сортировка: »).
            width: Ширина поля (в компактном виде по самому длинному варианту).
            on_change: Вызывается с новым значением после выбора пользователем.
            parent: Родитель.
        """
        super().__init__(
            label_text, required, compact=compact, width=width, parent=parent
        )
        self._choices = normalize(options)
        self._value = value
        self._placeholder = placeholder
        self._prefix = prefix
        self._compact = compact
        self._on_change = on_change
        self._popup: Optional[PopupList] = None
        self._inset = COMPACT_TEXT_INSET if compact else TEXT_INSET
        self._fixed_width = width
        self._fit_width()
        self.frame.setCursor(Qt.CursorShape.PointingHandCursor)

    @property
    def value(self) -> object:
        """Значение выбранного варианта (None, если ничего не выбрано)."""
        return self._value

    @property
    def choices(self) -> Sequence[Tuple[object, str]]:
        """Варианты (значение, подпись)."""
        return tuple(self._choices)

    def get(self) -> object:
        """Возвращает значение выбранного варианта."""
        return self._value

    def set(self, value: object) -> None:
        """Выбирает вариант по значению."""
        self._value = value
        self._refresh()

    def set_options(self, options: Sequence[OptionLike]) -> None:
        """Заменяет список вариантов."""
        self._choices = normalize(options)
        self._refresh()

    def _refresh(self) -> None:
        self._fit_width()
        self.frame.update()

    def shown_text(self) -> str:
        """Текст, который виден в поле (подпись выбранного или подсказка)."""
        text = self._label_of(self._value)
        return self._prefix + text if text else self._placeholder

    def _label_of(self, value: object) -> str:
        return next((text for item, text in self._choices if item == value), "")

    def _fit_width(self) -> None:
        """Подгоняет ширину фильтра под выбранное значение (как в макете)."""
        if self._compact and self._fixed_width is None:
            text = text_width(self.shown_text(), "body")
            inner = (
                text + COMPACT_TEXT_INSET + COMPACT_ARROW_GAP + ICON_SIZE + ICON_INSET
            )
            self.set_width(inner)

    # --- список ---

    @property
    def popup(self) -> Optional[PopupList]:
        """Открытый сейчас список или None."""
        return self._popup

    def _stage(self) -> Stage:
        """Что показать в списке: варианты, выбранное, обработчики выбора."""
        return self._choices, self._value, self._pick, None

    def frame_pressed(self, _event) -> None:
        if self._popup is not None:
            self._popup.close_list()
            return
        options, selected, on_pick, on_stage = self._stage()
        self._popup = PopupList(
            self.frame,
            options,
            selected,
            on_pick,
            self._closed,
            self.frame.box_rect(),
            on_stage,
        )
        self.frame.update()  # рамка становится голубой, пока список открыт

    def _pick(self, value: object) -> None:
        self._value = value
        self.clear_error()
        self._refresh()
        if self._on_change is not None:
            self._on_change(value)

    def _closed(self) -> None:
        self._popup = None
        self.frame.update()

    # --- рисование ---

    def frame_colors(self):
        """Голубая рамка только пока открыт список (а не пока поле «в фокусе»)."""
        if self._error is None and self._popup is not None:
            return palette().primary, None
        return super().frame_colors()

    def paint_content(self, painter: QPainter, box: QRectF) -> None:
        pal = palette()
        chosen = bool(self._label_of(self._value))
        color = (pal.ink_2 if self._compact else pal.ink) if chosen else pal.ink_3
        painter.setFont(font("body"))
        painter.setPen(qcolor(color))
        painter.drawText(
            box.adjusted(self._inset, 0, 0, 0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.shown_text(),
        )
        arrow = icon_pixmap("chevron-down", ICON_SIZE, pal.ink_3)
        painter.drawPixmap(
            round(box.right() - ICON_INSET - ICON_SIZE),
            round(box.center().y() - ICON_SIZE / 2),
            arrow,
        )
