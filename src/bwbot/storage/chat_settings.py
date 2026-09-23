"""Chat settings: silent mode and future per-chat options."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from bwbot.storage.json_store import CorruptStoreError, JsonStore

logger = logging.getLogger(__name__)

SILENT_KEY = "silent"


def _normalize_entry(entry: Any) -> dict[str, Any]:
    """The new format is a dict. A flat bool is left over from the old bot version."""
    if isinstance(entry, bool):
        return {SILENT_KEY: entry}
    return dict(entry) if isinstance(entry, dict) else {}


def _normalize_document(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    return {str(chat_id): _normalize_entry(entry) for chat_id, entry in data.items()}


class ChatSettingsRepository:
    """{ "<chat_id>": { "silent": true } } in a single JSON file.

    Also reads the old flat format { "<chat_id>": true } so that silent mode in
    chats is not reset when migrating from the previous version.
    """

    def __init__(self, path: Path) -> None:
        self._store = JsonStore(path)

    @property
    def path(self) -> Path:
        return self._store.path

    def get(self, chat_id: int) -> dict[str, Any]:
        data = _normalize_document(self._load())
        return data.get(str(chat_id), {})

    def is_silent(self, chat_id: int) -> bool:
        return bool(self.get(chat_id).get(SILENT_KEY, False))

    def set_silent(self, chat_id: int, enabled: bool) -> None:
        key = str(chat_id)

        def updater(data: Any) -> dict[str, Any]:
            normalized = _normalize_document(data)
            entry = normalized.get(key, {})
            entry[SILENT_KEY] = enabled
            normalized[key] = entry
            return normalized

        self._mutate(updater)

    def migrate(self) -> int:
        """Brings the file to the new format. Returns the number of fixed entries."""
        raw = self._load()
        if not isinstance(raw, dict):
            return 0
        normalized = _normalize_document(raw)
        changed = sum(1 for key, entry in normalized.items() if not isinstance(raw.get(key), dict))
        if changed:
            self._store.save(normalized)
        return changed

    def _load(self) -> Any:
        """A corrupt settings file must not stop moderation: we remember emptiness.

        We don't touch the file itself — let it stay for inspection; the very
        first write will rewrite it from scratch.
        """
        try:
            return self._store.load({})
        except CorruptStoreError:
            logger.exception("Chat settings file is corrupt: %s", self._store.path)
            return {}

    def _mutate(self, updater) -> None:
        try:
            self._store.mutate({}, updater)
        except CorruptStoreError:
            logger.exception(
                "Chat settings file is corrupt, rewriting it: %s", self._store.path
            )
            self._store.save(updater({}))
