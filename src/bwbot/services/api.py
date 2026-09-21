"""Узкий интерфейс к Telegram API: сервисам не нужен настоящий Bot."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Protocol


class ChatApi(Protocol):
    async def delete_message(self, chat_id: int, message_id: int) -> None: ...

    async def send_message(self, chat_id: int, text: str) -> None: ...


async def notify_all(api: ChatApi, chat_ids: Iterable[int], text: str) -> list[BaseException]:
    """Шлёт текст каждому адресату, не падая на отказе одного канала."""
    results = await asyncio.gather(
        *(api.send_message(chat_id, text) for chat_id in chat_ids),
        return_exceptions=True,
    )
    return [item for item in results if isinstance(item, BaseException)]
