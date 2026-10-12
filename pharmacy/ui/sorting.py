"""Виды сортировки таблицы «Моя аптечка» и их подвиды (направления).

Сначала выбирается вид сортировки (название, количество ...), затем подвид
(от А до Я или от Я до А и так далее). Подвиды подобраны по смыслу вида:
для текста это алфавит, для чисел «от большего к меньшему», для дат «сначала
новые» и так далее.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from pharmacy.utils.formatting import format_quantity

DEFAULT_SORT = "status"  # если сортировка не выбрана: по состоянию, это важнее всего


@dataclass(frozen=True)
class SortChoice:
    """Подвид сортировки.

    Attributes:
        value: Значение, которое понимает сервис товаров.
        label: Подпись в списке подвидов.
        caption: Короткая фиолетовая подпись в шапке столбца («А-Я»).
    """

    value: str
    label: str
    caption: str


@dataclass(frozen=True)
class SortKind:
    """Вид сортировки.

    Attributes:
        key: Короткое имя вида.
        label: Подпись в списке видов.
        short: Название вида в поле выбора («название»).
        column: Номер столбца таблицы, к которому относится вид (None, если
            у вида нет своего столбца).
        choices: Подвиды; первый включается, когда вид выбран впервые.
    """

    key: str
    label: str
    short: str
    column: Optional[int]
    choices: Tuple[SortChoice, ...]


ALPHABET = (
    SortChoice("{}", "от А до Я", "А-Я"),
    SortChoice("{}_desc", "от Я до А", "Я-А"),
)


def _alphabet(base: str) -> Tuple[SortChoice, ...]:
    return tuple(SortChoice(c.value.format(base), c.label, c.caption) for c in ALPHABET)


# Номера столбцов: Название 0, Дата добавления 1, Категория 2, Количество 3,
# Ед. изм. 4, Срок годности 5, Место хранения 6, Состояние 7.
SORT_KINDS: Tuple[SortKind, ...] = (
    SortKind(
        "status",
        "По состоянию",
        "состояние",
        7,
        (
            SortChoice("status", "сначала просроченные", "просроч."),
            SortChoice("status_ok", "сначала норма", "норма"),
        ),
    ),
    SortKind("name", "По названию", "название", 0, _alphabet("name")),
    SortKind(
        "quantity",
        "По количеству",
        "количество",
        3,
        (
            SortChoice("quantity_desc", "от большего к меньшему", "9-0"),
            SortChoice("quantity", "от меньшего к большему", "0-9"),
        ),
    ),
    SortKind(
        "expiry",
        "По сроку годности",
        "срок годности",
        5,
        (
            SortChoice("expiry", "сначала ближайшие", "ближе"),
            SortChoice("expiry_desc", "сначала самые дальние", "дальше"),
        ),
    ),
    SortKind("category", "По категории", "категория", 2, _alphabet("category")),
    SortKind("place", "По месту хранения", "место хранения", 6, _alphabet("place")),
    SortKind(
        "added",
        "По дате добавления",
        "дата добавления",
        1,
        (
            SortChoice("added", "сначала новые", "новые"),
            SortChoice("added_asc", "сначала старые", "старые"),
        ),
    ),
)

_BY_VALUE = {
    choice.value: (kind, choice) for kind in SORT_KINDS for choice in kind.choices
}
_BY_KEY = {kind.key: kind for kind in SORT_KINDS}
_BY_COLUMN = {kind.column: kind for kind in SORT_KINDS if kind.column is not None}


_quantity_range: Optional[Tuple[float, float]] = None


def set_quantity_range(low: Optional[float], high: Optional[float]) -> None:
    """Запоминает наименьшее и наибольшее количество в аптечке пользователя.

    По ним подписи сортировки по количеству показывают настоящие числа
    («3-23» и «23-3»), а не «0-9» и «9-0». Без товаров подписи прежние.
    """
    global _quantity_range
    _quantity_range = None if low is None or high is None else (low, high)


def caption_of(value: str) -> str:
    """Короткая подпись подвида; у сортировки по количеству это числа из аптечки."""
    choice = choice_of(value)
    if kind_of(value).key != "quantity" or _quantity_range is None:
        return choice.caption
    low, high = (format_quantity(number) for number in _quantity_range)
    return f"{high}-{low}" if value.endswith("_desc") else f"{low}-{high}"


def label_of(value: str) -> str:
    """Подпись подвида в списке; у количества добавлены числа («… (23-3)»)."""
    choice = choice_of(value)
    if kind_of(value).key != "quantity" or _quantity_range is None:
        return choice.label
    return f"{choice.label} ({caption_of(value)})"


def is_sort(value: object) -> bool:
    """Известно ли такое значение сортировки."""
    return value in _BY_VALUE


def kind_of(value: str) -> SortKind:
    """Вид, к которому относится значение сортировки."""
    return _BY_VALUE[value][0]


def choice_of(value: str) -> SortChoice:
    """Подвид по значению сортировки."""
    return _BY_VALUE[value][1]


def kind_by_key(key: str) -> SortKind:
    """Вид по его короткому имени."""
    return _BY_KEY[key]


def kind_for_column(column: int) -> Optional[SortKind]:
    """Вид сортировки для столбца таблицы (None, если столбец не сортируется)."""
    return _BY_COLUMN.get(column)


def toggled(value: str) -> str:
    """Другой подвид того же вида: «от А до Я» меняется на «от Я до А»."""
    kind = kind_of(value)
    values = [choice.value for choice in kind.choices]
    return values[(values.index(value) + 1) % len(values)]


def field_text(value: str) -> str:
    """Текст в поле выбора: «название (А-Я)»."""
    return f"{kind_of(value).short} ({caption_of(value)})"
