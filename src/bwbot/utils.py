"""Мелкие утилиты без зависимостей."""

from __future__ import annotations

TELEGRAM_MESSAGE_LIMIT = 4096


def normalize_word(word: str) -> str:
    return word.strip().lower()


def append_note(text: str, note: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> str:
    """Дописывает строку под сообщением, не вылезая за лимит Telegram.

    Отчёт об удалении содержит текст нарушителя и может быть длинным, поэтому
    при нехватке места жертвуем хвостом отчёта, а не пометкой о бане.
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


def chunk_text(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Режет текст на куски, не разрывая строки посередине, в предел лимита Telegram."""
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
