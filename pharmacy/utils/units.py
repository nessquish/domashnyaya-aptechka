"""Единицы измерения: единый список, значение по умолчанию и приведение вариантов."""

from typing import Dict

from pharmacy.errors import ValidationError

DEFAULT_UNIT = "шт."
# Единицы для выпадающего списка: первая подставляется по умолчанию.
UNITS = (DEFAULT_UNIT, "упак.", "табл.", "мг", "г", "мл", "фл.")

# Как люди пишут ту же единицу по-разному: все такие записи приводятся к одной,
# чтобы в аптечке не было «таб», «табл», «таблетки» одновременно.
_VARIANTS = {
    "шт.": "шт штука штуки штук",
    "упак.": "уп уп. упак упаковка упаковки",
    "табл.": "таб таб. табл таблетка таблетки таблеток",
    "мг": "мг.",
    "г": "г. гр гр. грамм",
    "мл": "мл.",
    "фл.": "фл флакон флаконы",
}
_ALIASES: Dict[str, str] = {
    alias: unit for unit, aliases in _VARIANTS.items() for alias in aliases.split()
}
_BY_LOWER = {unit.lower(): unit for unit in UNITS}


def normalize_unit(unit: str, field: str = "unit") -> str:
    """Приводит единицу измерения к одной из списка.

    Args:
        unit: Единица, которую выбрал или ввёл пользователь.
        field: Имя поля формы для сообщения об ошибке.

    Returns:
        Единица из ``UNITS``. Если единица не указана, «шт.».

    Raises:
        ValidationError: Если такой единицы в списке нет и на известный вариант
            написания она не похожа.
    """
    key = unit.strip().lower()
    if not key:
        return DEFAULT_UNIT
    found = _BY_LOWER.get(key) or _ALIASES.get(key)
    if found is None:
        raise ValidationError("Выберите единицу измерения из списка", field)
    return found
