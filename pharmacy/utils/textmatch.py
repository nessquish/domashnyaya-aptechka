"""Мягкое сравнение названий для поиска: без учёта регистра, ё и окончаний."""

import re
from typing import List

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
    common = 0
    for first, second in zip(query_word, word):
        if first != second:
            break
        common += 1
    return common >= max(MIN_COMMON, min(len(query_word), len(word)) - 2)


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
