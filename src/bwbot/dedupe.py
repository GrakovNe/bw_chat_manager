"""Repeat detection: pure logic, no Telegram and no files.

A repeat is a message from the same author in the same chat whose normalized
text looks like an already-kept message above the threshold and falls inside the
window.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher

DEFAULT_WINDOW_DAYS = 7
DEFAULT_THRESHOLD = 0.9

# How many messages of one author to keep in memory: a spam chain longer than
# this is still caught against the latest copies.
MAX_ENTRIES_PER_AUTHOR = 50

_SECONDS_PER_DAY = 86400

# The comparison runs inside the message handler, so the length of the compared
# slices is capped: 4096 characters against fifty entries is seconds in
# SequenceMatcher, while repeats must be caught within a frame. The tail beyond
# 600 characters does not affect the decision — a copy of an ad is visible from
# its beginning.
COMPARE_LIMIT = 600

# An underscore counts as a letter, not punctuation: `@username` still loses its
# hash and remains a word.
_PUNCTUATION = re.compile(r"[^\w\s]+", re.UNICODE)
_WHITESPACE = re.compile(r"\s+", re.UNICODE)


@dataclass(frozen=True)
class StoredPost:
    """An earlier kept message: only it takes part in the comparison."""

    message_id: int
    posted_at: float
    text: str


@dataclass(frozen=True)
class Repeat:
    """The most similar of the author's previous messages."""

    score: float
    message_id: int
    posted_at: float


def normalize(text: str) -> str:
    """Bring text to a form where "Garage!!!" and "garage" are the same.

    Case, punctuation, emoji and all whitespace are insignificant. Digits stay:
    building 3 and building 5 are different ads, and we tell them apart.
    """
    without_punctuation = _PUNCTUATION.sub(" ", text.lower())
    return _WHITESPACE.sub(" ", without_punctuation).strip()


def similarity(left: str, right: str, *, threshold: float = 0.0) -> float:
    """Similarity of two normalized texts, from 0 to 1.

    `autojunk=False` is required: by default SequenceMatcher declares commonly
    occurring characters in long strings "junk" and drops the score.

    `threshold` is a fast cutoff: `quick_ratio` is an upper bound on the real
    ratio, so if even it is below the threshold, an exact comparison is not
    needed.
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
    """Find the author's most similar message inside the window, otherwise None."""
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
