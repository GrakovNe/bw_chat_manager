"""Repeats: reports to administrators and deletion via the button."""

from __future__ import annotations

from dataclasses import replace

import pytest

from bwbot.dedupe import normalize
from bwbot.handlers import deletes as delete_handlers
from bwbot.services.moderation import ModerationService
from bwbot.storage.chat_settings import ChatSettingsRepository
from bwbot.storage.recent_posts import RecentPostsRepository
from bwbot.storage.words import WordRepository
from bwbot.utils import TELEGRAM_MESSAGE_LIMIT
from conftest import (
    ADMIN_ID,
    CHAT_ID,
    STRANGER_ID,
    FakeBot,
    FakeCallbackUpdate,
    FakeClock,
    FakeMessage,
    make_callback,
    make_context,
)

FIRST = "selling a garage in building 3"
COPY = "  Selling A Garage In Building 3!!! "
OTHER_POST = "selling a storage unit in building 7 urgently"
OTHER_USER = 555
DAY = 86400


@pytest.fixture(autouse=True)
def building_word(words_repo):
    """An allowed word is needed so messages pass moderation and get into the base."""
    words_repo.add("building")
    return words_repo


def delete_data(chat_id: int = CHAT_ID, message_id: int = 42) -> str:
    return f"del:{chat_id}:{message_id}"


async def post(deps, api, text: str, *, message_id: int = 1, user_id: int | None = STRANGER_ID):
    return await deps.moderation.handle_message(
        api, chat_id=CHAT_ID, message_id=message_id, text=text, user_id=user_id
    )


class TestRepeatReport:
    async def test_first_post_is_only_recorded(self, deps, api, bot: FakeBot, recent_posts_repo):
        await post(deps, api, FIRST)

        assert bot.sent == []
        assert [post_.text for post_ in recent_posts_repo.posts(CHAT_ID, STRANGER_ID)] == [
            normalize(FIRST)
        ]

    async def test_copy_is_reported_with_delete_button(self, deps, api, bot: FakeBot):
        await post(deps, api, FIRST, message_id=1)
        await post(deps, api, COPY, message_id=2)

        reports = [(text, buttons) for chat_id, text, buttons in bot.sent if chat_id == ADMIN_ID]
        assert len(reports) == 1
        text, buttons = reports[0]
        assert COPY in text or normalize(COPY) in text
        assert "100%" in text
        assert buttons == ((deps.settings.dup_delete_label, delete_data(message_id=2)),)

    async def test_copy_is_not_deleted_by_itself(self, deps, api, bot: FakeBot):
        await post(deps, api, FIRST, message_id=1)
        decision = await post(deps, api, COPY, message_id=2)

        assert not decision.deletes
        assert bot.deleted == []

    async def test_same_text_from_another_author_is_quiet(self, deps, api, bot: FakeBot):
        await post(deps, api, FIRST, message_id=1)
        await post(deps, api, COPY, message_id=2, user_id=OTHER_USER)

        assert [chat_id for chat_id, _, _ in bot.sent if chat_id == ADMIN_ID] == []

    async def test_different_post_is_quiet(self, deps, api, bot: FakeBot):
        await post(deps, api, FIRST, message_id=1)
        await post(deps, api, OTHER_POST, message_id=2)

        assert [chat_id for chat_id, _, _ in bot.sent if chat_id == ADMIN_ID] == []

    async def test_repeat_outside_the_window_is_quiet(
        self, deps, api, bot: FakeBot, clock: FakeClock
    ):
        await post(deps, api, FIRST, message_id=1)
        clock.advance(days=deps.settings.dup_window_days + 1)
        await post(deps, api, COPY, message_id=2)

        assert [chat_id for chat_id, _, _ in bot.sent if chat_id == ADMIN_ID] == []

    async def test_repeat_inside_the_window_is_reported(
        self, deps, api, bot: FakeBot, clock: FakeClock
    ):
        await post(deps, api, FIRST, message_id=1)
        clock.advance(days=deps.settings.dup_window_days - 1)
        await post(deps, api, COPY, message_id=2)

        assert len([text for chat_id, text, _ in bot.sent if chat_id == ADMIN_ID]) == 1

    async def test_report_ages_the_matched_post(self, deps, api, bot: FakeBot, clock: FakeClock):
        await post(deps, api, FIRST, message_id=1)
        clock.advance(days=3)
        await post(deps, api, COPY, message_id=2)

        text = next(text for chat_id, text, _ in bot.sent if chat_id == ADMIN_ID)
        assert "3 days ago" in text

    async def test_report_template_comes_from_settings(self, settings, api, bot: FakeBot):
        deps_settings = replace(settings, dup_report="dup {score}% from {user_label}")
        service = ModerationService(
            deps_settings,
            _words(settings),
            _chat_settings(settings),
            _recent_posts(settings),
            FakeClock(),
        )
        await service.handle_message(
            api,
            chat_id=CHAT_ID,
            message_id=1,
            text=FIRST,
            user_label="vasya",
            user_id=STRANGER_ID,
        )
        await service.handle_message(
            api,
            chat_id=CHAT_ID,
            message_id=2,
            text=COPY,
            user_label="vasya",
            user_id=STRANGER_ID,
        )

        text = next(text for chat_id, text, _ in bot.sent if chat_id == ADMIN_ID)
        assert text == "dup 100% from vasya"

    async def test_deleted_message_is_not_recorded(self, deps, api, recent_posts_repo):
        await post(deps, api, "selling a garage without an address at all")

        assert recent_posts_repo.posts(CHAT_ID, STRANGER_ID) == []

    async def test_reply_is_not_recorded(self, deps, api, bot: FakeBot, recent_posts_repo):
        await deps.moderation.handle_message(
            api, chat_id=CHAT_ID, message_id=1, text=FIRST, is_reply=True, user_id=STRANGER_ID
        )

        assert recent_posts_repo.posts(CHAT_ID, STRANGER_ID) == []
        assert bot.sent == []

    async def test_short_message_is_not_recorded(self, deps, api, recent_posts_repo):
        await post(deps, api, "garage 3")

        assert recent_posts_repo.posts(CHAT_ID, STRANGER_ID) == []

    async def test_post_without_author_is_not_recorded(
        self, deps, api, bot: FakeBot, recent_posts_repo
    ):
        await post(deps, api, FIRST, message_id=1, user_id=None)
        await post(deps, api, COPY, message_id=2, user_id=None)

        assert recent_posts_repo.posts(CHAT_ID, STRANGER_ID) == []
        assert bot.sent == []

    async def test_report_failure_does_not_break_moderation(
        self, settings, api, bot: FakeBot
    ) -> None:
        from bwbot.services.moderation import ModerationService

        bot.fail_sending_to = {ADMIN_ID}
        service = ModerationService(
            settings, _words(settings), _chat_settings(settings), _recent_posts(settings)
        )
        await service.handle_message(
            api, chat_id=CHAT_ID, message_id=1, text=FIRST, user_id=STRANGER_ID
        )
        decision = await service.handle_message(
            api, chat_id=CHAT_ID, message_id=2, text=COPY, user_id=STRANGER_ID
        )

        assert not decision.deletes

    async def test_huge_copy_is_reported_within_telegram_limit(self, deps, api, bot: FakeBot):
        long_copy = "selling a garage in building 3 " + "listing details " * 1200

        await post(deps, api, long_copy, message_id=1)
        await post(deps, api, long_copy, message_id=2)

        reports = [text for chat_id, text, _ in bot.sent if chat_id == ADMIN_ID]
        assert len(reports) == 1
        assert len(reports[0]) <= TELEGRAM_MESSAGE_LIMIT
        # We clip the offender's text, not the report: the template tail must stay.
        assert "…" in reports[0]
        assert "match" in reports[0].splitlines()[-1]


class TestDeleteButton:
    async def test_admin_press_deletes_the_message(self, deps, bot: FakeBot):
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text="Suspected repeat")

        await delete_handlers.on_callback(
            make_callback(delete_data(), report=report), make_context(bot), deps=deps
        )

        assert bot.deleted == [(CHAT_ID, 42)]
        assert bot.answers == [("cb-1", deps.settings.dup_deleted_reply)]

    async def test_report_is_updated_and_button_removed(self, deps, bot: FakeBot):
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text="Suspected repeat")

        await delete_handlers.on_callback(
            make_callback(delete_data(), report=report), make_context(bot), deps=deps
        )

        assert len(bot.edited) == 1
        chat_id, message_id, text, buttons = bot.edited[0]
        assert (chat_id, message_id) == (ADMIN_ID, 42)
        assert text.startswith("Suspected repeat")
        assert "boss" in text
        assert buttons == ()

    async def test_stranger_press_does_nothing(self, deps, bot: FakeBot):
        await delete_handlers.on_callback(
            make_callback(delete_data(), by_id=STRANGER_ID), make_context(bot), deps=deps
        )

        assert bot.deleted == []
        assert bot.answers == [("cb-1", deps.settings.not_admin_reply)]

    @pytest.mark.parametrize("data", [None, "", "ban:-100:200", "del:abc:1", "del:-100:0"])
    async def test_broken_button_is_answered_but_ignored(self, deps, bot: FakeBot, data):
        await delete_handlers.on_callback(make_callback(data), make_context(bot), deps=deps)

        assert bot.deleted == []
        assert bot.answers == [("cb-1", deps.settings.dup_broken_reply)]

    async def test_failed_delete_keeps_the_button(self, deps, bot: FakeBot):
        bot.fail_deleting = (CHAT_ID, 42)
        bot.delete_error = "BadRequest: message to delete not found"
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text="Suspected repeat")

        await delete_handlers.on_callback(
            make_callback(delete_data(), report=report), make_context(bot), deps=deps
        )

        assert bot.edited == []
        assert len(bot.answers) == 1
        assert deps.settings.dup_delete_failed_reply in bot.answers[0][1]
        assert "not found" in bot.answers[0][1]

    async def test_report_without_text_is_still_deleted(self, deps, bot: FakeBot):
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text=None)

        await delete_handlers.on_callback(
            make_callback(delete_data(), report=report), make_context(bot), deps=deps
        )

        assert bot.deleted == [(CHAT_ID, 42)]
        assert bot.edited == []

    async def test_callback_query_absent_is_ignored(self, deps, bot: FakeBot):
        await delete_handlers.on_callback(
            FakeCallbackUpdate(callback_query=None), make_context(bot), deps=deps
        )

        assert bot.deleted == []
        assert bot.answers == []

    async def test_unreadable_report_does_not_undo_the_delete(self, deps, bot: FakeBot):
        bot.fail_editing = True
        report = FakeMessage(message_id=42, chat_id=ADMIN_ID, text="Suspected repeat")

        await delete_handlers.on_callback(
            make_callback(delete_data(), report=report), make_context(bot), deps=deps
        )

        assert bot.deleted == [(CHAT_ID, 42)]
        assert bot.answers == [("cb-1", deps.settings.dup_deleted_reply)]
        assert bot.edited == []

    async def test_callback_without_message_is_still_deleted(self, deps, bot: FakeBot):
        update = make_callback(delete_data())
        update.callback_query.message = None

        await delete_handlers.on_callback(update, make_context(bot), deps=deps)

        assert bot.deleted == [(CHAT_ID, 42)]
        assert bot.edited == []


def _words(settings) -> WordRepository:
    return WordRepository(settings.words_file)


def _chat_settings(settings) -> ChatSettingsRepository:
    return ChatSettingsRepository(settings.chat_settings_file)


def _recent_posts(settings) -> RecentPostsRepository:
    return RecentPostsRepository(settings.recent_posts_file, window_days=settings.dup_window_days)
