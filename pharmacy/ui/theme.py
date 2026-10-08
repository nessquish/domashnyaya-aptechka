"""Оформление: цвета, размеры и шрифты из макета Figma.

Все числа, которые определяют внешний вид, собраны здесь. Виджеты и экраны
берут значения отсюда и не содержат своих «магических» чисел.

Светлая палитра взята из макета. Тёмной палитры в макете нет, она подобрана
к светлой по тем же ролям цветов.
"""

from dataclasses import dataclass
from typing import Dict, Tuple

LIGHT_THEME = "light"
DARK_THEME = "dark"


@dataclass(frozen=True)
class Palette:
    """Набор цветов темы. Каждое поле отвечает за одну роль в интерфейсе."""

    bg: str  # фон окна
    side: str  # боковое меню
    card: str  # карточки и модальные окна
    line: str  # границы карточек и таблиц
    line_soft: str  # тонкие разделители внутри карточек
    input_line: str  # граница поля ввода
    input_bg: str  # фон поля ввода и обычной кнопки
    ink: str  # основной текст
    ink_2: str  # второстепенный текст
    ink_3: str  # подсказки и неактивный текст
    brand_ink: str  # название приложения и заголовки на экранах входа
    primary: str  # главный акцентный цвет
    primary_soft: str  # светлая подложка акцента (выбранный пункт, иконки)
    primary_ink: str  # текст на светлой подложке акцента
    on_primary: str  # текст на акцентном цвете
    red: str
    red_bg: str
    red_ring: str  # обводка вокруг поля с ошибкой
    red_line: str  # граница кнопки «Удалить»
    amber: str
    amber_bg: str
    green: str
    green_bg: str
    gray_bg: str  # нейтральная плашка
    table_head: str  # шапка таблицы
    tabs_bg: str  # подложка переключателя вкладок
    unread_bg: str  # непрочитанное уведомление, выбранная строка
    bulk_bg: str  # панель действий над выбранными строками
    checkbox_line: str
    hero_from: str  # градиент левой части экрана входа
    hero_to: str
    overlay: str  # затемнение под модальным окном
    shadow: str  # цвет теней


LIGHT = Palette(
    bg="#F6F7FC",
    side="#EFF1FB",
    card="#FFFFFF",
    line="#E4E6F0",
    line_soft="#F0F1F7",
    input_line="#DCDDF0",
    input_bg="#FFFFFF",
    ink="#262A45",
    ink_2="#5B5F77",
    ink_3="#8E91A6",
    brand_ink="#2F3260",
    primary="#5F57E8",
    primary_soft="#DAD7FC",
    primary_ink="#4B43D1",
    on_primary="#FFFFFF",
    red="#D3415E",
    red_bg="#FDE4E9",
    red_ring="#FBE3E8",
    red_line="#F3B9C5",
    amber="#B07415",
    amber_bg="#FFF0CC",
    green="#2D8A52",
    green_bg="#DEF5E6",
    gray_bg="#EEEFF5",
    table_head="#F7F8FC",
    tabs_bg="#ECEDF7",
    unread_bg="#FAFAFF",
    bulk_bg="#F3F2FF",
    checkbox_line="#C9CBDD",
    hero_from="#EEEEFD",
    hero_to="#F3F4FC",
    overlay="#1A1B30",
    shadow="#1E2050",
)

DARK = Palette(
    bg="#14152A",
    side="#1A1B33",
    card="#1F2140",
    line="#2E3055",
    line_soft="#282A4B",
    input_line="#3A3C63",
    input_bg="#181A33",
    ink="#ECEDF8",
    ink_2="#AAADC8",
    ink_3="#7F82A1",
    brand_ink="#ECEDF8",
    primary="#7A72F2",
    primary_soft="#3B3880",
    primary_ink="#D3D0FF",
    on_primary="#FFFFFF",
    # Цветные плашки и значки: пастельный текст на приглушённой подложке того
    # же оттенка. Достаточно светлые, чтобы читаться, но не режут глаз на тёмном.
    red="#F29BB0",
    red_bg="#5E3550",
    red_ring="#5A3047",
    red_line="#94566B",
    amber="#F3D499",
    amber_bg="#5C4E36",
    green="#92DDB6",
    green_bg="#305549",
    gray_bg="#34375C",
    table_head="#242645",
    tabs_bg="#25274A",
    unread_bg="#25274B",
    bulk_bg="#2A2B5A",
    checkbox_line="#4C4E75",
    hero_from="#1D1F3F",
    hero_to="#191B36",
    overlay="#05060F",
    shadow="#000000",
)

_PALETTES: Dict[str, Palette] = {LIGHT_THEME: LIGHT, DARK_THEME: DARK}
_active_name = LIGHT_THEME

# Размер текста: ключ -> (подпись, во сколько раз крупнее макета).
TEXT_SIZES: Dict[str, Tuple[str, float]] = {
    "normal": ("Обычный", 1.1),
    "medium": ("Средний", 1.25),
    "large": ("Большой", 1.4),
}
DEFAULT_TEXT_SIZE = "normal"
_text_size = DEFAULT_TEXT_SIZE


def set_text_size(name: str) -> None:
    """Выбирает размер текста (``normal``, ``medium`` или ``large``).

    Шрифты читают масштаб при создании виджетов, поэтому после смены
    размера экран нужно построить заново.

    Raises:
        ValueError: Если такого размера нет.
    """
    global _text_size
    if name not in TEXT_SIZES:
        raise ValueError(f"Неизвестный размер текста: {name}")
    _text_size = name


def text_size_name() -> str:
    """Возвращает выбранный размер текста."""
    return _text_size


def scaled(pixels: int) -> int:
    """Увеличивает размер шрифта из макета по выбранному размеру текста."""
    return max(round(pixels * TEXT_SIZES[_text_size][1]), 1)


def text_scale() -> float:
    """Возвращает масштаб текста (1.0 соответствует размерам макета)."""
    return TEXT_SIZES[_text_size][1]


def window_width() -> int:
    """Минимальная ширина окна: при крупном тексте окно шире, чтобы всё помещалось."""
    normal = TEXT_SIZES[DEFAULT_TEXT_SIZE][1]
    return round(WINDOW_MIN_WIDTH * text_scale() / normal)


def sidebar_width() -> int:
    """Ширина боковой панели растёт вместе с текстом, чтобы пункты не были тесными."""
    return round(SIDEBAR_WIDTH * text_scale())


def set_theme(name: str) -> None:
    """Выбирает тему оформления (``light`` или ``dark``).

    Виджеты читают палитру при создании, поэтому после смены темы экран
    нужно построить заново.

    Raises:
        ValueError: Если такой темы нет.
    """
    global _active_name
    if name not in _PALETTES:
        raise ValueError(f"Неизвестная тема: {name}")
    _active_name = name


def theme_name() -> str:
    """Возвращает название выбранной темы."""
    return _active_name


def palette() -> Palette:
    """Возвращает палитру выбранной темы."""
    return _PALETTES[_active_name]


def mix(first: str, second: str, share: float) -> str:
    """Смешивает два цвета.

    Args:
        first: Основной цвет вида ``#RRGGBB``.
        second: Добавляемый цвет.
        share: Доля второго цвета от 0 до 1.

    Returns:
        Цвет вида ``#RRGGBB``.
    """
    a, b = hex_to_rgb(first), hex_to_rgb(second)
    mixed = tuple(round(x + (y - x) * share) for x, y in zip(a, b))
    return "#{:02X}{:02X}{:02X}".format(*mixed)


def hex_to_rgb(color: str) -> Tuple[int, int, int]:
    """Переводит цвет ``#RRGGBB`` в тройку чисел от 0 до 255."""
    color = color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


# Размеры из макета (в пикселях).
WINDOW_WIDTH = 1160
WINDOW_HEIGHT = 660
WINDOW_MIN_WIDTH = 960  # окно можно сузить до половины экрана 1920×1080
WINDOW_MIN_HEIGHT = 520
SIDEBAR_WIDTH = 190
CONTENT_PADDING_X = 28
CONTENT_PADDING_Y = 22

CONTROL_HEIGHT = 32  # поле ввода, кнопка, выпадающий список
CONTROL_HEIGHT_SMALL = 26
CONTROL_HEIGHT_LARGE = 36
CONTROL_RADIUS = 7
CARD_RADIUS = 10
MODAL_RADIUS = 12
BADGE_RADIUS = 9

# Места под тени вокруг нарисованных виджетов (тень выходит за границу фигуры).
SHADOW_PAD = 4
CARD_SHADOW_PAD = 6
MODAL_SHADOW_PAD = 36  # большая тень окна входа и модальных окон

# Высота строки текста по стилям для размеров «обычный, средний, большой».
# Это размеры прежней вёрстки: по ним расставлены все отступы макета, поэтому
# высота строки не зависит от того, как шрифт округляется в системе.
LINE_HEIGHTS: Dict[str, Tuple[int, int, int]] = {
    "display": (26, 30, 34),
    "title": (28, 33, 34),
    "heading": (24, 26, 30),
    "section": (19, 21, 24),
    "brand": (16, 20, 21),
    "lead": (16, 20, 21),
    "lead_medium": (16, 20, 21),
    "value": (16, 20, 21),
    "product_title": (21, 24, 26),
    "body": (16, 19, 20),
    "body_medium": (16, 19, 20),
    "body_strong": (16, 19, 20),
    "small": (15, 16, 19),
    "small_medium": (15, 16, 19),
    "caption": (15, 16, 19),
    "label": (15, 16, 19),
    "badge": (15, 16, 19),
    "number": (28, 34, 39),
    "sidebar_title": (21, 26, 28),
    "user_name": (16, 19, 20),
    "counter": (15, 16, 19),
    "modal_title": (21, 24, 26),
    "strong": (16, 19, 20),
}


def line_height(style: str) -> int:
    """Высота строки текста в пикселях для стиля и выбранного размера текста."""
    return LINE_HEIGHTS[style][tuple(TEXT_SIZES).index(_text_size)]


# Начертания: название стиля -> (размер в пикселях, насыщенность).
TYPOGRAPHY: Dict[str, Tuple[int, int]] = {
    "display": (20, 800),
    "title": (21, 700),
    "heading": (18, 700),
    "section": (14, 700),
    "brand": (13, 700),
    "lead": (13, 400),
    "lead_medium": (13, 500),
    "value": (13, 500),
    "product_title": (16, 700),
    "body": (12, 400),
    "body_medium": (12, 500),
    "body_strong": (12, 600),
    "small": (11, 400),
    "small_medium": (11, 500),
    "caption": (11, 400),
    "label": (11, 400),
    "badge": (11, 500),
    "number": (22, 700),
    "sidebar_title": (17, 800),
    "user_name": (12, 700),
    "counter": (11, 700),
    "modal_title": (16, 700),
    "strong": (12, 700),
}
