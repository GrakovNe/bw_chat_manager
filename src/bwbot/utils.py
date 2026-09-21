"""Мелкие утилиты без зависимостей."""

from __future__ import annotations

TELEGRAM_MESSAGE_LIMIT = 4096


def normalize_word(word: str) -> str:
    return word.strip().lower()


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
