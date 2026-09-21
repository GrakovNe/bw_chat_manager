"""Узкий интерфейс к Telegram API: сервисам не нужен настоящий Bot."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from typing import Protocol

# Кнопка под сообщением: подпись и callback_data, которая вернётся в хендлере.
Button = tuple[str, str]


class ApiError(RuntimeError):
    """Telegram отказал в действии. Текст понятен человеку и показуется администраторам."""


class ChatApi(Protocol):
    async def delete_message(self, chat_id: int, message_id: int) -> None: ...

    async def send_message(
        self, chat_id: int, text: str, buttons: Sequence[Button] = ()
    ) -> None: ...

    async def edit_message_text(
        self, chat_id: int, message_id: int, text: str, buttons: Sequence[Button] = ()
    ) -> None: ...

    async def answer_callback(self, callback_id: str, text: str) -> None: ...

    async def ban_chat_member(self, chat_id: int, user_id: int) -> None: ...


async def notify_all(
    api: ChatApi,
    chat_ids: Iterable[int],
    text: str,
    buttons: Sequence[Button] = (),
) -> list[BaseException]:
    """Шлёт текст каждому адресату, не падая на отказе одного канала."""
    results = await asyncio.gather(
        *(api.send_message(chat_id, text, buttons) for chat_id in chat_ids),
        return_exceptions=True,
    )
    return [item for item in results if isinstance(item, BaseException)]
