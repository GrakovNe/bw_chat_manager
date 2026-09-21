"""Настройки чатов: тихий режим и будущие per-chat опции."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bwbot.storage.json_store import JsonStore

SILENT_KEY = "silent"


class ChatSettingsRepository:
    """{ "<chat_id>": { "silent": true } } в одном JSON-файле."""

    def __init__(self, path: Path) -> None:
        self._store = JsonStore(path)

    @property
    def path(self) -> Path:
        return self._store.path

    def get(self, chat_id: int) -> dict[str, Any]:
        data = self._store.load({})
        entry = data.get(str(chat_id))
        return dict(entry) if isinstance(entry, dict) else {}

    def is_silent(self, chat_id: int) -> bool:
        return bool(self.get(chat_id).get(SILENT_KEY, False))

    def set_silent(self, chat_id: int, enabled: bool) -> None:
        key = str(chat_id)

        def updater(data: dict[str, Any]) -> None:
            entry = data.get(key)
            if not isinstance(entry, dict):
                entry = {}
            entry[SILENT_KEY] = enabled
            data[key] = entry

        self._store.mutate({}, updater)
