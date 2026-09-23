"""Parsing the BAN button's callback_data — this data comes from outside, so we are picky."""

from __future__ import annotations

import pytest

from bwbot.callbacks import BanTarget, ban_button, parse_ban_target

CHAT = -1002136766439
USER = 777


def test_button_carries_target() -> None:
    target = BanTarget(chat_id=CHAT, user_id=USER)
    label, data = ban_button(target, "BAN")

    assert label == "BAN"
    assert data == f"ban:{CHAT}:{USER}"
    assert len(data.encode()) <= 64


def test_round_trip() -> None:
    target = BanTarget(chat_id=CHAT, user_id=USER)
    assert parse_ban_target(ban_button(target, "BAN")[1]) == target


@pytest.mark.parametrize(
    "data",
    [
        None,
        "",
        "ban",
        "ban:",
        "ban:-100",
        "ban:-100:",
        "unban:-100:200",
        "BAN:-100:200",
        "ban:abc:200",
        "ban:-100:abc",
        "ban:-100:200:300",
        "ban:-100:-200",
        "ban:0:200",
        "ban: 100:200",
        "ban:100 :200",
        "ban:1_0:200",
        "ban:١٢٣:200",
        "ban:-100:200 ",
        "ban:-100:200\n",
        "ban:-100:+200",
    ],
)
def test_garbage_is_rejected(data: str | None) -> None:
    assert parse_ban_target(data) is None


@pytest.mark.parametrize("user_id", [1, 2**40])
def test_positive_users_are_accepted(user_id: int) -> None:
    assert parse_ban_target(f"ban:{CHAT}:{user_id}") == BanTarget(chat_id=CHAT, user_id=user_id)
