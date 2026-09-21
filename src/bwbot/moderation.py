"""Чистая логика модерации: никаких зависимостей от Telegram."""

from __future__ import annotations

from collections.abc import Container
from dataclasses import dataclass
from enum import Enum


class Action(Enum):
    IGNORE_EMPTY = "ignore_empty"
    IGNORE_REPLY = "ignore_reply"
    IGNORE_SHORT = "ignore_short"
    ALLOW = "allow"
    DELETE = "delete"


@dataclass(frozen=True)
class Decision:
    action: Action
    matched_word: str | None = None

    @property
    def deletes(self) -> bool:
        return self.action is Action.DELETE


def decide(
    text: str | None,
    *,
    allowed_words: Container[str],
    min_length: int,
    is_reply: bool = False,
) -> Decision:
    """Одно сообщение -> одно решение. Порядок проверок наследует поведение исходного бота."""
    if is_reply:
        return Decision(Action.IGNORE_REPLY)
    if text is None or not text.strip():
        return Decision(Action.IGNORE_EMPTY)
    if len(text) < min_length:
        return Decision(Action.IGNORE_SHORT)

    lowered = text.lower()
    for word in allowed_words:
        if word and word in lowered:
            return Decision(Action.ALLOW, matched_word=word)
    return Decision(Action.DELETE)
