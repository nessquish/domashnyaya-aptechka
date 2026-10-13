"""Выбор сортировки в два шага: сначала вид, потом подвид, в одном и том же списке."""

from typing import Callable, List, Optional, Tuple

from PySide6.QtWidgets import QWidget

from pharmacy.ui.sorting import (
    SORT_KINDS,
    SortKind,
    field_text,
    kind_by_key,
    kind_of,
    label_of,
)
from pharmacy.ui.widgets.popup import Option, Stage
from pharmacy.ui.widgets.select import Select

BACK = "__back__"
BACK_LABEL = "‹  Назад к видам сортировки"


class SortSelect(Select):
    """Поле сортировки.

    По нажатию открывается список видов (по состоянию, по названию ...). Выбор
    вида не закрывает список: он тут же меняется на подвиды этого вида (от А до Я
    и от Я до А). После выбора подвида список закрывается. Дополнительных окон нет.
    """

    def __init__(
        self,
        value: str,
        on_change: Optional[Callable[[object], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Создаёт поле.

        Args:
            value: Выбранная сортировка (значение подвида).
            on_change: Вызывается с новым значением после выбора подвида.
            parent: Родитель.
        """
        options = [
            (choice.value, field_text(choice.value))
            for kind in SORT_KINDS
            for choice in kind.choices
        ]
        super().__init__(
            options,
            value,
            compact=True,
            prefix="Сортировка: ",
            on_change=on_change,
            parent=parent,
        )

    # --- две ступени списка ---

    def _stage(self) -> Stage:
        return self._kinds_stage()

    def _kinds_stage(self) -> Stage:
        kinds: List[Option] = [(kind.key, kind.label) for kind in SORT_KINDS]
        return kinds, kind_of(self._value).key, self._pick, self._to_choices

    def _to_choices(self, key: object) -> Optional[Tuple]:
        """Выбран вид: список меняется на подвиды этого вида."""
        kind: SortKind = kind_by_key(str(key))
        options: List[Option] = [(BACK, BACK_LABEL)]
        options += [(choice.value, label_of(choice.value)) for choice in kind.choices]
        selected = self._value if kind_of(self._value) is kind else None
        return options, selected, self._pick, self._from_choices

    def _from_choices(self, value: object) -> Optional[Tuple]:
        """В списке подвидов: «Назад» возвращает к видам, остальное выбирает подвид."""
        if value == BACK:
            return self._kinds_stage()
        return None
