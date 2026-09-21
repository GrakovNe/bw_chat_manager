"""Извлечение из Update того, что нужно сервисам."""

from __future__ import annotations

from dataclasses import dataclass

from telegram import Update


@dataclass(frozen=True)
class IncomingMessage:
    chat_id: int
    message_id: int
    text: str | None
    is_reply: bool
    user_id: int | None
    user_label: str


def from_update(update: Update) -> IncomingMessage | None:
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return None
    user = update.effective_user
    return IncomingMessage(
        chat_id=chat.id,
        message_id=message.message_id,
        text=message.text,
        is_reply=message.reply_to_message is not None,
        user_id=user.id if user else None,
        user_label=(user.username or user.full_name) if user else "аноним",
    )
