"""Поиск повторов: чистая логика, без Telegram и файлов.

Повтором считается сообщение того же автора в том же чате, чей нормализованный
текст похож на уже оставленное сообщение выше порога и лежит внутри окна.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher

DEFAULT_WINDOW_DAYS = 7
DEFAULT_THRESHOLD = 0.9

# Сколько сообщений одного автора держать в памяти: спам-цепочка длиннее этого
# всё равно ловится по последним копиям.
MAX_ENTRIES_PER_AUTHOR = 50

_SECONDS_PER_DAY = 86400

# Подчёркивание считаем буквой, а не пунктуацией: `@username` всё равно теряет
# решётку и остаётся словом.
_PUNCTUATION = re.compile(r"[^\w\s]+", re.UNICODE)
_WHITESPACE = re.compile(r"\s+", re.UNICODE)


@dataclass(frozen=True)
class StoredPost:
    """Ранее оставленное сообщение: только оно и участвует в сравнении."""

    message_id: int
    posted_at: float
    text: str


@dataclass(frozen=True)
class Repeat:
    """Самое похожее из прежних сообщений автора."""

    score: float
    message_id: int
    posted_at: float


def normalize(text: str) -> str:
    """Приводит текст к виду, в котором «Гараж!!!» и «гараж» — одно и то же.

    Регистр, пунктуация, эмодзи и все пробельные символы не значимы. Цифры
    остаются: корпус 3 и корпус 5 — разные объявления, их различаем.
    """
    without_punctuation = _PUNCTUATION.sub(" ", text.lower())
    return _WHITESPACE.sub(" ", without_punctuation).strip()


def similarity(left: str, right: str) -> float:
    """Похожесть двух нормализованных текстов от 0 до 1.

    `autojunk=False` обязателен: по умолчанию SequenceMatcher объявляет
    «мусором» часто встречающиеся символы в длинных строках и роняет оценку.
    """
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def find_repeat(
    posts: Iterable[StoredPost],
    text: str,
    *,
    now: float,
    window_days: int = DEFAULT_WINDOW_DAYS,
    threshold: float = DEFAULT_THRESHOLD,
) -> Repeat | None:
    """Ищет самое похожее сообщение автора внутри окна, иначе None."""
    needle = normalize(text)
    if not needle:
        return None

    oldest_allowed = now - window_days * _SECONDS_PER_DAY
    best: Repeat | None = None
    for post in posts:
        if not post.text or post.posted_at < oldest_allowed or post.posted_at > now:
            continue
        score = similarity(needle, post.text)
        if score >= threshold and (best is None or score > best.score):
            best = Repeat(score=score, message_id=post.message_id, posted_at=post.posted_at)
    return best
