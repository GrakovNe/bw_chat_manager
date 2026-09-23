"""Button format and callback_data parsing. Pure logic, no Telegram."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bwbot.services.api import Button

BAN_ACTION = "ban"
DELETE_ACTION = "del"
_SEPARATOR = ":"

# ASCII digits only: `int("1_0")` equals 10, and callback_data comes from outside.
_DIGITS = re.compile(r"-?[0-9]+")


@dataclass(frozen=True)
class BanTarget:
    """Who to ban and where: the message author and the chat where it was written."""

    chat_id: int
    user_id: int

    @property
    def callback_data(self) -> str:
        return _join(BAN_ACTION, self.chat_id, self.user_id)


@dataclass(frozen=True)
class DeleteTarget:
    """Which message to delete. The repeat is searched in the same chat where it appeared."""

    chat_id: int
    message_id: int

    @property
    def callback_data(self) -> str:
        return _join(DELETE_ACTION, self.chat_id, self.message_id)


def ban_button(target: BanTarget, label: str) -> Button:
    return (label, target.callback_data)


def delete_button(target: DeleteTarget, label: str) -> Button:
    return (label, target.callback_data)


def parse_ban_target(data: str | None) -> BanTarget | None:
    """Parses `ban:<chat_id>:<user_id>`. Anything else — silently None."""
    numbers = _parse_two_numbers(data, BAN_ACTION)
    if numbers is None:
        return None

    chat_id, user_id = numbers
    if user_id <= 0:
        return None
    return BanTarget(chat_id=chat_id, user_id=user_id)


def parse_delete_target(data: str | None) -> DeleteTarget | None:
    """Parses `del:<chat_id>:<message_id>`. Anything else — silently None."""
    numbers = _parse_two_numbers(data, DELETE_ACTION)
    if numbers is None:
        return None

    chat_id, message_id = numbers
    if message_id <= 0:
        return None
    return DeleteTarget(chat_id=chat_id, message_id=message_id)


def _join(action: str, first: int, second: int) -> str:
    return action + _SEPARATOR + str(first) + _SEPARATOR + str(second)


def _parse_two_numbers(data: str | None, action: str) -> tuple[int, int] | None:
    if not data:
        return None

    parts = data.split(_SEPARATOR)
    if len(parts) != 3 or parts[0] != action:
        return None

    if not _DIGITS.fullmatch(parts[1]) or not _DIGITS.fullmatch(parts[2]):
        return None

    first, second = int(parts[1]), int(parts[2])
    if first == 0:
        return None
    return first, second
