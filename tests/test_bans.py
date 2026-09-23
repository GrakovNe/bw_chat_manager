"""Banning via the button: the service and the callback handler."""

from __future__ import annotations

import pytest

from bwbot.callbacks import BanTarget
from bwbot.config import Settings
from bwbot.handlers import bans as ban_handlers
from bwbot.services.bans import BanService
from bwbot.telegram_api import TelegramApi
from conftest import (
    ADMIN_ID,
    CHAT_ID,
    STRANGER_ID,
    FakeBot,
    FakeCallbackUpdate,
    FakeMessage,
    make_callback,
    make_context,
)

REPORT_TEXT = f"Deleted in chat {CHAT_ID} from stranger: selling a garage in another complex"


def ban_data(chat_id: int = CHAT_ID, user_id: int = STRANGER_ID) -> str:
    return f"ban:{chat_id}:{user_id}"


class TestBanService:
    async def test_ban_calls_telegram(self, settings: Settings, api) -> None:
        result = await BanService(settings).ban(api, BanTarget(CHAT_ID, STRANGER_ID), by="boss")

        assert result.ok is True
        assert result.message == settings.ban_done_reply
        assert api.bot.banned == [(CHAT_ID, STRANGER_ID)]  # type: ignore[attr-defined]

    async def test_admin_is_never_banned(self, settings: Settings, api) -> None:
        result = await BanService(settings).ban(api, BanTarget(CHAT_ID, ADMIN_ID), by="boss")

        assert result.ok is False
        assert result.message == settings.ban_admin_reply
        assert api.bot.banned == []  # type: ignore[attr-defined]

    async def test_refusal_from_telegram_becomes_human_message(self, settings: Settings) -> None:
        bot = FakeBot(fail_banning=(CHAT_ID, STRANGER_ID), ban_error="Forbidden: not enough rights")
        result = await BanService(settings).ban(
            TelegramApi(bot), BanTarget(CHAT_ID, STRANGER_ID), by="boss"
        )

        assert result.ok is False
        assert result.message.startswith(settings.ban_failed_reply)
        assert "not enough rights" in result.message


class TestBanCallback:
    async def test_admin_press_bans_in_the_chat_of_the_original_message(
        self, deps, bot: FakeBot
    ) -> None:
        # The report lives in the admin's DMs, but the ban must hit the working chat.
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text=REPORT_TEXT)
        update = make_callback(ban_data(), report=report)

        await ban_handlers.on_callback(update, make_context(bot), deps=deps)

        assert bot.banned == [(CHAT_ID, STRANGER_ID)]
        assert bot.answers == [("cb-1", deps.settings.ban_done_reply)]

    async def test_report_is_updated_and_button_removed(self, deps, bot: FakeBot) -> None:
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text=REPORT_TEXT)
        update = make_callback(ban_data(), report=report)

        await ban_handlers.on_callback(update, make_context(bot), deps=deps)

        assert len(bot.edited) == 1
        chat_id, message_id, text, buttons = bot.edited[0]
        assert (chat_id, message_id) == (ADMIN_ID, 42)
        assert text.startswith(REPORT_TEXT)
        assert "boss" in text
        assert buttons == ()

    async def test_stranger_press_does_nothing(self, deps, bot: FakeBot) -> None:
        update = make_callback(ban_data(), by_id=STRANGER_ID, username="curious")

        await ban_handlers.on_callback(update, make_context(bot), deps=deps)

        assert bot.banned == []
        assert bot.edited == []
        assert bot.answers == [("cb-1", deps.settings.not_admin_reply)]

    async def test_anonymous_press_does_nothing(self, deps, bot: FakeBot) -> None:
        update = make_callback(ban_data(), by_id=None)

        await ban_handlers.on_callback(update, make_context(bot), deps=deps)

        assert bot.banned == []
        assert bot.answers == [("cb-1", deps.settings.not_admin_reply)]

    @pytest.mark.parametrize("data", [None, "", "ban:abc:1", "unban:-100:200"])
    async def test_broken_button_is_answered_but_ignored(
        self, deps, bot: FakeBot, data: str | None
    ) -> None:
        await ban_handlers.on_callback(make_callback(data), make_context(bot), deps=deps)

        assert bot.banned == []
        assert bot.answers == [("cb-1", deps.settings.ban_broken_reply)]

    async def test_stale_button_on_admin_is_refused(self, deps, bot: FakeBot) -> None:
        # The report may predate the ban-admins rule — the button is still on it.
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text=REPORT_TEXT)
        update = make_callback(ban_data(user_id=ADMIN_ID), report=report)

        await ban_handlers.on_callback(update, make_context(bot), deps=deps)

        assert bot.banned == []
        assert bot.edited == []
        assert bot.answers == [("cb-1", deps.settings.ban_admin_reply)]

    async def test_failed_ban_keeps_the_button(self, deps, bot: FakeBot) -> None:
        bot.fail_banning = (CHAT_ID, STRANGER_ID)
        bot.ban_error = "Forbidden: bot is not administrator"
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text=REPORT_TEXT)

        await ban_handlers.on_callback(
            make_callback(ban_data(), report=report), make_context(bot), deps=deps
        )

        assert bot.edited == []
        assert len(bot.answers) == 1
        assert "not administrator" in bot.answers[0][1]

    async def test_unreadable_report_does_not_undo_the_ban(self, deps, bot: FakeBot) -> None:
        """Telegram refused to edit the old message — the ban is not undone by that."""
        bot.fail_editing = True
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text=REPORT_TEXT)

        await ban_handlers.on_callback(
            make_callback(ban_data(), report=report), make_context(bot), deps=deps
        )

        assert bot.banned == [(CHAT_ID, STRANGER_ID)]
        assert bot.answers == [("cb-1", deps.settings.ban_done_reply)]
        assert bot.edited == []

    async def test_report_without_text_is_still_banned(self, deps, bot: FakeBot) -> None:
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text=None)

        await ban_handlers.on_callback(
            make_callback(ban_data(), report=report), make_context(bot), deps=deps
        )

        assert bot.banned == [(CHAT_ID, STRANGER_ID)]
        assert bot.edited == []

    async def test_callback_without_message_is_still_banned(self, deps, bot: FakeBot) -> None:
        update = make_callback(ban_data(), report=None)
        update.callback_query.message = None  # type: ignore[union-attr]

        await ban_handlers.on_callback(update, make_context(bot), deps=deps)

        assert bot.banned == [(CHAT_ID, STRANGER_ID)]
        assert bot.edited == []

    async def test_callback_query_absent_is_ignored(self, deps, bot: FakeBot) -> None:
        await ban_handlers.on_callback(
            FakeCallbackUpdate(callback_query=None), make_context(bot), deps=deps
        )

        assert bot.banned == []
        assert bot.answers == []
