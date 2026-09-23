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

# Сравнение крутится в обработчике сообщений, поэтому длину сравниваемых кусков
# ограничиваем: 4096 символов против пятидесяти записей — это секунды в
# SequenceMatcher, а ловить повторы нужно в кадре. Хвост дальше 600 символов
# на решение не влияет: копию объявления видно по началу.
COMPARE_LIMIT = 600

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


def similarity(left: str, right: str, *, threshold: float = 0.0) -> float:
    """Похожесть двух нормализованных текстов от 0 до 1.

    `autojunk=False` обязателен: по умолчанию SequenceMatcher объявляет
    «мусором» часто встречающиеся символы в длинных строках и роняет оценку.

    `threshold` — быстрая отсечка: `quick_ratio` является верхней оценкой
    настоящего отношения, и если уже она ниже порога, точное сравнение не нужно.
    """
    left, right = left[:COMPARE_LIMIT], right[:COMPARE_LIMIT]
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    matcher = SequenceMatcher(None, left, right, autojunk=False)
    if matcher.quick_ratio() < threshold:
        return 0.0
    return matcher.ratio()


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

    def within_window(post: StoredPost) -> bool:
        return bool(post.text) and oldest_allowed <= post.posted_at <= now

    def as_repeat(post: StoredPost) -> Repeat:
        return Repeat(
            score=similarity(needle, post.text, threshold=threshold),
            message_id=post.message_id,
            posted_at=post.posted_at,
        )

    candidates = (as_repeat(post) for post in posts if within_window(post))
    return max(
        (repeat for repeat in candidates if repeat.score >= threshold),
        key=lambda repeat: repeat.score,
        default=None,
    )
