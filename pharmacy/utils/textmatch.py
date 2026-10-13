"""Мягкое сравнение названий для поиска: без учёта регистра, ё и окончаний."""

import re
from os.path import commonprefix
from typing import Callable, List, TypeVar

_WORD = re.compile(r"\w+", re.UNICODE)
MIN_STEM = 3  # слово короче этого не считается началом более длинного запроса
MIN_COMMON = 4  # сколько букв должно совпасть у разных форм одного слова


def _normalize(text: str) -> str:
    return text.casefold().replace("ё", "е")


def _words(text: str) -> List[str]:
    return _WORD.findall(_normalize(text))


def _same_word(query_word: str, word: str) -> bool:
    """Слово запроса подходит слову названия: начало, форма или окончание другое.

    «витамины» подходит к «Витамин D», «парацетамола» к «Парацетамол».
    """
    if word.startswith(query_word):
        return True
    if len(word) >= MIN_STEM and query_word.startswith(word):
        return True
    if len(query_word) >= 5 and query_word[:-2] in word:
        return True  # основа слова внутри другого: «витамины» в «поливитаминный»
    common = len(commonprefix([query_word, word]))
    return common >= max(MIN_COMMON, min(len(query_word), len(word)) - 2)


T = TypeVar("T")


def find_matching(
    items: List[T], text_of: Callable[[T], str], query: str, limit: int
) -> List[T]:
    """Первые ``limit`` элементов, текст которых подходит под запрос."""
    return [item for item in items if name_matches(text_of(item), query)][:limit]


def name_matches(text: str, query: str) -> bool:
    """Подходит ли ``text`` под запрос ``query``.

    Подходит, если запрос целиком встречается внутри текста или каждое слово
    запроса подходит какому-нибудь слову текста (с учётом окончаний).

    Args:
        text: Название товара, категория, заметка и т. п.
        query: Введённый пользователем текст.
    """
    needle = _normalize(query).strip()
    if not needle:
        return False
    if needle in _normalize(text):
        return True
    text_words = _words(text)
    query_words = _words(needle)
    return bool(query_words) and all(
        any(_same_word(q, word) for word in text_words) for q in query_words
    )
