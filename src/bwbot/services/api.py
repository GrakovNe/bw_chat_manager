"""Narrow interface to the Telegram API: services don't need a real Bot."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Sequence
from typing import Protocol

# A button under a message: a label and the callback_data returned in the handler.
Button = tuple[str, str]


class ApiError(RuntimeError):
    """Telegram refused an action. The text is human-readable and shown to administrators."""


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
    """Sends text to every recipient without failing on one broken channel."""
    results = await asyncio.gather(
        *(api.send_message(chat_id, text, buttons) for chat_id in chat_ids),
        return_exceptions=True,
    )
    return [item for item in results if isinstance(item, BaseException)]
