"""Список разрешённых слов (дома и дворы BW)."""

from __future__ import annotations

import threading
from pathlib import Path

from bwbot.storage.json_store import write_text_atomic
from bwbot.utils import normalize_word


class WordRepository:
    """Плоский файл: одно слово в строке. Пустые строки игнорируются, регистр не значим."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def all(self) -> frozenset[str]:
        with self._lock:
            return self._read()

    def add(self, word: str) -> bool:
        """Добавляет слово. False — если оно уже было или пустое."""
        cleaned = normalize_word(word)
        if not cleaned:
            return False
        with self._lock:
            words = self._read()
            if cleaned in words:
                return False
            words.add(cleaned)
            self._write(words)
            return True

    def remove(self, word: str) -> bool:
        """Удаляет слово. False — если его не было."""
        cleaned = normalize_word(word)
        with self._lock:
            words = self._read()
            if cleaned not in words:
                return False
            words.discard(cleaned)
            self._write(words)
            return True

    def _read(self) -> set[str]:
        try:
            raw = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return set()
        return {normalize_word(line) for line in raw.splitlines() if line.strip()}

    def _write(self, words: set[str]) -> None:
        body = "\n".join(sorted(words))
        write_text_atomic(self._path, f"{body}\n" if body else "")
