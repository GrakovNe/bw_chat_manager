"""Админ-операции над списком слов. Синхронные и без Telegram — ради тестов."""

from __future__ import annotations

from dataclasses import dataclass

from bwbot.storage.words import WordRepository
from bwbot.utils import chunk_text, normalize_word


@dataclass(frozen=True)
class AdminResult:
    ok: bool
    message: str
    extra_chunks: tuple[str, ...] = ()


@dataclass
class WordAdminService:
    words: WordRepository

    def add_word(self, raw_word: str | None) -> AdminResult:
        word = normalize_word(raw_word or "")
        if not word:
            return AdminResult(ok=False, message="Использование: /add <слово>")
        if not self.words.add(word):
            return AdminResult(ok=False, message=f"Слово «{word}» уже есть в списке.")
        return AdminResult(ok=True, message=f"Слово «{word}» добавлено в список.")

    def delete_word(self, raw_word: str | None) -> AdminResult:
        word = normalize_word(raw_word or "")
        if not word:
            return AdminResult(ok=False, message="Использование: /delete_word <слово>")
        if not self.words.remove(word):
            return AdminResult(ok=False, message=f"Слова «{word}» нет в списке.")
        return AdminResult(ok=True, message=f"Слово «{word}» удалено из списка.")

    def list_words(self) -> AdminResult:
        words = sorted(self.words.all())
        if not words:
            return AdminResult(ok=True, message="Список слов пуст.")
        chunks = chunk_text(f"Разрешённые слова ({len(words)}):\n" + "\n".join(words))
        first, *rest = chunks
        return AdminResult(ok=True, message=first, extra_chunks=tuple(rest))
