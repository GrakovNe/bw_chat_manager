"""Small dependency-free utilities."""

from __future__ import annotations

TELEGRAM_MESSAGE_LIMIT = 4096


def normalize_word(word: str) -> str:
    return word.strip().lower()


def append_note(text: str, note: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> str:
    """Append a line under a message without going over the Telegram limit.

    A deletion report embeds the offender's text and can be long, so when space
    runs short we sacrifice the tail of the report, not the note about the
    administrator's action.
    """
    if not note:
        return text[:limit]

    separator = "\n\n"
    if len(text) + len(separator) + len(note) <= limit:
        return f"{text}{separator}{note}"

    keep = limit - len(separator) - len(note)
    if keep <= 0:
        return note[:limit]
    return f"{text[:keep].rstrip()}{separator}{note}"


def clip(text: str, limit: int) -> str:
    """Trim text to the limit, marking the cut with an ellipsis."""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit == 1:
        return "…"
    return f"{text[: limit - 1].rstrip()}…"


def chunk_text(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Split text into chunks within the Telegram limit without breaking a line mid-way."""
    if len(text) <= limit:
        return [text] if text else []

    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.split("\n"):
        extra = len(line) + (1 if current else 0)
        if current and size + extra > limit:
            chunks.append("\n".join(current))
            current, size = [line], len(line)
        else:
            current.append(line)
            size += extra
    if current:
        chunks.append("\n".join(current))
    return chunks


_SECONDS_PER_DAY = 86400


def human_age(then: float, now: float) -> str:
    """Message age in English: "today", "yesterday", "4 days ago"."""
    days = int((now - then) // _SECONDS_PER_DAY)
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    return f"{days} days ago"
