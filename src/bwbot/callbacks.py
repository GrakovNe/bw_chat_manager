"""Формат кнопок и разбор callback_data. Чистая логика, без Telegram."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bwbot.services.api import Button

BAN_ACTION = "ban"
_SEPARATOR = ":"

# Только ASCII-цифры: `int("1_0")` равно 10, а callback_data приходит извне.
_DIGITS = re.compile(r"-?[0-9]+")


@dataclass(frozen=True)
class BanTarget:
    """Кого и где банить: автор сообщения и чат, где оно было написано."""

    chat_id: int
    user_id: int

    @property
    def callback_data(self) -> str:
        return BAN_ACTION + _SEPARATOR + str(self.chat_id) + _SEPARATOR + str(self.user_id)


def ban_button(target: BanTarget, label: str) -> Button:
    return (label, target.callback_data)


def parse_ban_target(data: str | None) -> BanTarget | None:
    """Разбирает `ban:<chat_id>:<user_id>`. Всё остальное — молча None."""
    if not data:
        return None

    parts = data.split(_SEPARATOR)
    if len(parts) != 3 or parts[0] != BAN_ACTION:
        return None

    raw_chat, raw_user = parts[1], parts[2]
    if not _DIGITS.fullmatch(raw_chat) or not _DIGITS.fullmatch(raw_user):
        return None

    chat_id = int(raw_chat)
    user_id = int(raw_user)
    if chat_id == 0 or user_id <= 0:
        return None

    return BanTarget(chat_id=chat_id, user_id=user_id)
