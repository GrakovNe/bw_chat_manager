"""Admin operations on the word list. Synchronous and Telegram-free — for the sake of tests."""

from __future__ import annotations

from dataclasses import dataclass

from bwbot.storage.words import WordRepository
from bwbot.utils import chunk_text, normalize_word


@dataclass(frozen=True)
class AdminResult:
    ok: bool
    message: str
    extra_chunks: tuple[str, ...] = ()


@dataclass(frozen=True)
class WordAdminService:
    words: WordRepository

    def add_word(self, raw_word: str | None) -> AdminResult:
        word = normalize_word(raw_word or "")
        if not word:
            return AdminResult(ok=False, message="Usage: /add <word>")
        if not self.words.add(word):
            return AdminResult(ok=False, message=f"Word {word!r} is already in the list.")
        return AdminResult(ok=True, message=f"Word {word!r} added to the list.")

    def delete_word(self, raw_word: str | None) -> AdminResult:
        word = normalize_word(raw_word or "")
        if not word:
            return AdminResult(ok=False, message="Usage: /delete_word <word>")
        if not self.words.remove(word):
            return AdminResult(ok=False, message=f"Word {word!r} is not in the list.")
        return AdminResult(ok=True, message=f"Word {word!r} removed from the list.")

    def list_words(self) -> AdminResult:
        words = sorted(self.words.all())
        if not words:
            return AdminResult(ok=True, message="The word list is empty.")
        chunks = chunk_text(f"Allowed words ({len(words)}):\n" + "\n".join(words))
        first, *rest = chunks
        return AdminResult(ok=True, message=first, extra_chunks=tuple(rest))
