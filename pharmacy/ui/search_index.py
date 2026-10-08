"""Реестр для поиска по программе: разделы и настройки с ключевыми словами.

Каждая запись знает, как называется, под какими словами её ищут и куда ведёт.
Товары в реестре не лежат: их ищет ``ProductService.search_products``.
"""

from dataclasses import dataclass
from typing import List, Tuple

from pharmacy.ui import sections

SECTION = "section"  # раздел главного меню
SETTINGS = "settings"  # раздел экрана «Настройки»
PRODUCT = "product"  # товар в «Моей аптечке»

# Ключи разделов настроек (совпадают с ключами в screens/settings.py).
APPEARANCE = "appearance"
NOTIFICATIONS = "notifications"
DATA = "data"
ACCOUNT = "account"
ABOUT = "about"

MAX_RESULTS = 10  # в каждой группе


@dataclass(frozen=True)
class Target:
    """Куда ведёт результат поиска.

    Attributes:
        kind: ``section``, ``settings`` или ``product``.
        value: Название раздела меню, ключ раздела настроек или номер товара.
    """

    kind: str
    value: object


@dataclass(frozen=True)
class SearchEntry:
    """Запись реестра.

    Attributes:
        keywords: Слова, по которым запись находится (кроме названия).
        title: Название результата.
        path: Путь для подписи («Настройки → Внешний вид → Тема»).
        target: Куда перейти по нажатию.
    """

    keywords: Tuple[str, ...]
    title: str
    path: str
    target: Target


def _section(title: str, name: str, *keywords: str) -> SearchEntry:
    return SearchEntry(keywords, title, name, Target(SECTION, name))


def _setting(title: str, key: str, group_title: str, *keywords: str) -> SearchEntry:
    path = f"Настройки → {group_title}"
    if title != group_title:
        path += f" → {title}"
    return SearchEntry(keywords, title, path, Target(SETTINGS, key))


_APPEARANCE = "Внешний вид"
_NOTIFY = "Уведомления"
_DATA = "Данные"
_ACCOUNT = "Аккаунт"
_ABOUT = "О программе"

SEARCH_INDEX: Tuple[SearchEntry, ...] = (
    # Разделы главного меню.
    _section("Главная", sections.HOME, "сводка", "обзор", "старт"),
    _section(
        "Моя аптечка", sections.MY_KIT, "товары", "лекарства", "запасы", "таблица"
    ),
    _section(
        "Список покупок", sections.SHOPPING, "купить", "корзина", "магазин", "докупить"
    ),
    _section(
        "Уведомления",
        sections.NOTIFICATIONS,
        "просрочено",
        "срок годности",
        "низкий остаток",
    ),
    _section("История", sections.HISTORY, "действия", "журнал", "лог", "записи"),
    _section("Настройки", sections.SETTINGS, "параметры", "опции"),
    # Внешний вид.
    _setting("Внешний вид", APPEARANCE, _APPEARANCE, "оформление", "вид"),
    _setting(
        "Тема",
        APPEARANCE,
        _APPEARANCE,
        "тёмная",
        "темная",
        "светлая",
        "системная",
        "ночной",
        "цвета",
    ),
    _setting(
        "Масштаб",
        APPEARANCE,
        _APPEARANCE,
        "размер окна",
        "dpi",
        "ползунок",
        "крупнее",
        "мельче",
    ),
    _setting(
        "Размер шрифта",
        APPEARANCE,
        _APPEARANCE,
        "текст",
        "мелкий",
        "крупный",
        "средний",
        "шрифт",
    ),
    _setting(
        "Значки в меню", APPEARANCE, _APPEARANCE, "иконки", "меню", "боковая панель"
    ),
    _setting("Акцентный цвет", APPEARANCE, _APPEARANCE, "цвет", "палитра"),
    # Уведомления.
    _setting(
        "Уведомления", NOTIFICATIONS, _NOTIFY, "включить", "выключить", "оповещения"
    ),
    _setting(
        "Срок годности истёк", NOTIFICATIONS, _NOTIFY, "просроченные", "просрочка"
    ),
    _setting(
        "Скоро истекает срок",
        NOTIFICATIONS,
        _NOTIFY,
        "за сколько дней",
        "предупреждать",
        "заранее",
    ),
    _setting(
        "Низкий остаток", NOTIFICATIONS, _NOTIFY, "порог", "мало", "заканчивается"
    ),
    # Данные.
    _setting(
        "Экспорт данных",
        DATA,
        _DATA,
        "csv",
        "json",
        "excel",
        "xlsx",
        "выгрузить",
        "сохранить в файл",
        "резервная копия",
    ),
    _setting("Импорт данных", DATA, _DATA, "загрузить", "из файла", "csv", "json"),
    _setting("Очистить историю", DATA, _DATA, "удалить историю", "стереть"),
    _setting(
        "Сбросить все данные", DATA, _DATA, "сброс", "удалить всё", "очистить аптечку"
    ),
    # Аккаунт.
    _setting("Имя пользователя", ACCOUNT, _ACCOUNT, "имя", "профиль"),
    _setting("Логин", ACCOUNT, _ACCOUNT, "войти", "профиль"),
    _setting(
        "Электронная почта", ACCOUNT, _ACCOUNT, "email", "e-mail", "почта", "адрес"
    ),
    _setting("Сменить пароль", ACCOUNT, _ACCOUNT, "пароль", "безопасность"),
    _setting("Выйти из аккаунта", ACCOUNT, _ACCOUNT, "выход", "разлогиниться"),
    _setting("Удалить аккаунт", ACCOUNT, _ACCOUNT, "удаление", "стереть аккаунт"),
    # О программе.
    _setting(
        "О программе",
        ABOUT,
        _ABOUT,
        "версия",
        "дата сборки",
        "разработчик",
        "автор",
        "руководство",
        "github",
        "справка",
    ),
)


def _matches(entry: SearchEntry, needle: str) -> int:
    """Оценка совпадения: 0 — не подходит, чем больше, тем лучше."""
    title = entry.title.casefold()
    if title.startswith(needle):
        return 4
    if needle in title:
        return 3
    words = [w.casefold() for w in entry.keywords]
    if any(w.startswith(needle) for w in words):
        return 2
    if any(needle in w for w in words):
        return 1
    return 0


def search_sections(query: str, limit: int = MAX_RESULTS) -> List[SearchEntry]:
    """Ищет разделы и настройки по названию и ключевым словам.

    Args:
        query: Введённый текст (регистр не важен).
        limit: Сколько записей вернуть не больше.

    Returns:
        Подходящие записи: сначала те, у кого название начинается с запроса.
    """
    needle = query.strip().casefold()
    if not needle:
        return []
    scored = [
        (_matches(entry, needle), index, entry)
        for index, entry in enumerate(SEARCH_INDEX)
    ]
    found = [item for item in scored if item[0] > 0]
    found.sort(key=lambda item: (-item[0], item[1]))
    return [entry for _score, _index, entry in found[:limit]]
