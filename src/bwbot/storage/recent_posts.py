"""Недавние оставленные сообщения — по ним ищем повторы.

Файл `recent_posts.json`: `{ "<chat_id>": { "<user_id>": [post, ...] } }`, где
post — `{"id": <message_id>, "at": <epoch>, "text": <нормализованный текст>}`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bwbot.dedupe import MAX_ENTRIES_PER_AUTHOR, StoredPost, normalize
from bwbot.storage.json_store import CorruptStoreError, JsonStore

logger = logging.getLogger(__name__)

_SECONDS_PER_DAY = 86400


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _parse_post(entry: Any) -> StoredPost | None:
    """Одна запись списка. Мусор вместо записи — None, а не исключение."""
    if not isinstance(entry, dict):
        return None
    message_id = entry.get("id")
    posted_at = _as_float(entry.get("at"))
    text = entry.get("text")
    if not isinstance(message_id, int) or isinstance(message_id, bool):
        return None
    if posted_at is None or not isinstance(text, str) or not text.strip():
        return None
    return StoredPost(message_id=message_id, posted_at=posted_at, text=text)


def _parse_chat(entry: Any) -> dict[str, list[StoredPost]]:
    if not isinstance(entry, dict):
        return {}
    posts: dict[str, list[StoredPost]] = {}
    for user_id, raw_posts in entry.items():
        if not isinstance(raw_posts, list):
            continue
        parsed = [post for post in (_parse_post(item) for item in raw_posts) if post is not None]
        if parsed:
            posts[str(user_id)] = parsed
    return posts


class RecentPostsRepository:
    """Хранит последние оставленные сообщения, чтобы сравнивать с ними новые.

    Окно и лимит на автора применяются при каждой записи, поэтому файл не
    разрастается, а чтение не думает о том, что пора чистить.
    """

    def __init__(
        self,
        path: Path,
        *,
        window_days: int,
        max_entries: int = MAX_ENTRIES_PER_AUTHOR,
    ) -> None:
        self._store = JsonStore(path)
        self._window_days = window_days
        self._max_entries = max_entries

    @property
    def path(self) -> Path:
        return self._store.path

    def posts(self, chat_id: int, user_id: int) -> list[StoredPost]:
        chat = self._load().get(str(chat_id), {})
        return list(chat.get(str(user_id), ()))

    def record(
        self,
        chat_id: int,
        user_id: int,
        message_id: int,
        text: str,
        *,
        at: float | None = None,
    ) -> None:
        moment = time.time() if at is None else at
        normalized = normalize(text)
        if not normalized:
            return

        chat_key, user_key = str(chat_id), str(user_id)
        oldest_allowed = moment - self._window_days * _SECONDS_PER_DAY

        def updater(document: dict[str, dict[str, list[StoredPost]]]) -> None:
            chat = document.get(chat_key, {})
            fresh = [post for post in chat.get(user_key, []) if post.posted_at >= oldest_allowed]
            fresh.append(StoredPost(message_id=message_id, posted_at=moment, text=normalized))
            chat[user_key] = fresh[-self._max_entries :]
            document[chat_key] = chat

        self._update(updater)

    def prune(self, *, now: float | None = None) -> int:
        """Убирает записи вне окна целиком. Возвращает число удалённых сообщений."""
        moment = time.time() if now is None else now
        oldest_allowed = moment - self._window_days * _SECONDS_PER_DAY
        removed = 0

        def updater(document: dict[str, dict[str, list[StoredPost]]]) -> None:
            nonlocal removed
            for chat_key, chat in list(document.items()):
                for user_key, posts in list(chat.items()):
                    kept = [post for post in posts if post.posted_at >= oldest_allowed]
                    removed += len(posts) - len(kept)
                    if kept:
                        chat[user_key] = kept
                    else:
                        del chat[user_key]
                if not chat:
                    del document[chat_key]

        self._update(updater)
        return removed

    def _update(self, updater: Callable[[dict[str, dict[str, list[StoredPost]]]], None]) -> None:
        """Правит файл под локом. Повреждённый файл лечится перезаписью.

        На целом файле действует `mutate`: чтение и запись в одном локе. Если
        разбор упал, менять нечего — пишем заново с пустого документа, иначе
        бот навсегда останется без памяти о повторах.
        """

        def json_updater(data: Any) -> Any:
            document = _parse_document(data)
            updater(document)
            return _dump_document(document)

        try:
            self._store.mutate({}, json_updater)
        except CorruptStoreError:
            logger.exception("Файл повторов повреждён, записываем заново: %s", self._store.path)
            document: dict[str, dict[str, list[StoredPost]]] = {}
            updater(document)
            self._store.save(_dump_document(document))

    def _load(self) -> dict[str, dict[str, list[StoredPost]]]:
        try:
            return _parse_document(self._store.load({}))
        except CorruptStoreError:
            # Повреждённый файл повторов не должен останавливать модерацию:
            # помним ровно то, что успели записать заново.
            logger.exception("Файл повторов повреждён: %s", self._store.path)
            return {}


def _parse_document(data: Any) -> dict[str, dict[str, list[StoredPost]]]:
    if not isinstance(data, dict):
        return {}
    document: dict[str, dict[str, list[StoredPost]]] = {}
    for chat_id, chat in data.items():
        parsed = _parse_chat(chat)
        if parsed:
            document[str(chat_id)] = parsed
    return document


def _dump_document(document: dict[str, dict[str, list[StoredPost]]]) -> dict[str, Any]:
    """Обратно в JSON-совместимую структуру: StoredPost сериализовать не умеет."""
    return {
        chat_id: {
            user_id: [
                {"id": post.message_id, "at": post.posted_at, "text": post.text} for post in posts
            ]
            for user_id, posts in chat.items()
        }
        for chat_id, chat in document.items()
    }
