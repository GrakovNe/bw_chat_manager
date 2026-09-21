"""Настройки чатов: тихий режим и будущие per-chat опции."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bwbot.storage.json_store import JsonStore

SILENT_KEY = "silent"


def _normalize_entry(entry: Any) -> dict[str, Any]:
    """Новый формат — словарь. Плоский bool остался от старой версии бота."""
    if isinstance(entry, bool):
        return {SILENT_KEY: entry}
    return dict(entry) if isinstance(entry, dict) else {}


def _normalize_document(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    return {str(chat_id): _normalize_entry(entry) for chat_id, entry in data.items()}


class ChatSettingsRepository:
    """{ "<chat_id>": { "silent": true } } в одном JSON-файле.

    Читает и старый плоский формат { "<chat_id": true }, чтобы при переезде
    с прежней версии тихий режим в чатах не сбросился.
    """

    def __init__(self, path: Path) -> None:
        self._store = JsonStore(path)

    @property
    def path(self) -> Path:
        return self._store.path

    def get(self, chat_id: int) -> dict[str, Any]:
        data = _normalize_document(self._store.load({}))
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

        self._store.mutate({}, updater)

    def migrate(self) -> int:
        """Приводит файл к новому формату. Возвращает число исправленных записей."""
        raw = self._store.load({})
        if not isinstance(raw, dict):
            return 0
        normalized = _normalize_document(raw)
        changed = sum(1 for key, entry in normalized.items() if not isinstance(raw.get(key), dict))
        if changed:
            self._store.save(normalized)
        return changed
