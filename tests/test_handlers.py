"""Handler tests: only the Telegram wrapper, the logic is verified separately."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from bwbot.config import Settings
from bwbot.deps import Deps
from bwbot.handlers import admin as admin_handlers
from bwbot.handlers import bans as ban_handlers
from bwbot.handlers import deletes as delete_handlers
from bwbot.handlers import messages as message_handlers
from bwbot.handlers import silent as silent_handlers
from bwbot.handlers.extract import from_update
from bwbot.services.admin import WordAdminService
from bwbot.services.bans import BanService
from bwbot.services.deletes import DeleteService
from bwbot.services.moderation import ModerationService
from bwbot.storage.words import WordRepository
from conftest import (
    ADMIN_ID,
    CHAT_ID,
    STRANGER_ID,
    FakeBot,
    FakeChat,
    FakeUpdate,
    FakeUser,
    make_context,
    make_update,
)

BAD_TEXT = "selling a garage in another complex"


def make_deps(
    settings: Settings,
    words_repo: WordRepository,
    chat_settings_repo,
    recent_posts_repo,
) -> Deps:
    return Deps(
        settings=settings,
        words=words_repo,
        chat_settings=chat_settings_repo,
        moderation=ModerationService(settings, words_repo, chat_settings_repo, recent_posts_repo),
        word_admin=WordAdminService(words_repo),
        bans=BanService(settings),
        deletes=DeleteService(settings),
    )


class TestAdminCommands:
    async def test_start_answers(self, deps, bot: FakeBot):
        update = make_update("/start", user_id=ADMIN_ID)
        await admin_handlers.start(update, make_context(bot), deps=deps)
        assert update.effective_message.replies == [admin_handlers.START_TEXT]

    async def test_add_by_stranger_is_refused(self, deps, bot: FakeBot):
        update = make_update("/add", user_id=STRANGER_ID)
        await admin_handlers.add_word(update, make_context(bot, ["building 5"]), deps=deps)
        assert update.effective_message.replies == [deps.settings.not_admin_reply]
        assert deps.words.all() == frozenset()
        assert bot.sent == []

    async def test_add_by_admin_writes_file_and_replies(self, deps, bot: FakeBot):
        update = make_update("/add", user_id=ADMIN_ID, username="boss")
        await admin_handlers.add_word(update, make_context(bot, [" Building 5 "]), deps=deps)
        assert deps.words.all() == frozenset({"building 5"})
        assert "building 5" in update.effective_message.replies[0]

    async def test_add_notifies_other_admins_only(
        self, settings, words_repo: WordRepository, chat_settings_repo, recent_posts_repo
    ):
        bot = FakeBot()
        wider = replace(settings, admin_ids=frozenset({ADMIN_ID, 300}))
        deps = make_deps(wider, words_repo, chat_settings_repo, recent_posts_repo)
        update = make_update("/add", user_id=ADMIN_ID, username="boss")

        await admin_handlers.add_word(update, make_context(bot, ["yard"]), deps=deps)

        assert [chat_id for chat_id, _, _ in bot.sent] == [300]
        assert "boss" in bot.sent[0][1]
        assert "yard" in bot.sent[0][1]

    async def test_add_without_argument_shows_usage(self, deps, bot: FakeBot):
        update = make_update("/add", user_id=ADMIN_ID)
        await admin_handlers.add_word(update, make_context(bot, []), deps=deps)
        assert "/add" in update.effective_message.replies[0]
        assert deps.words.all() == frozenset()

    async def test_add_takes_the_whole_argument_as_one_word(self, deps, bot: FakeBot, words_repo):
        update = make_update("/add building 3", user_id=ADMIN_ID)
        await admin_handlers.add_word(update, make_context(bot, ["building", "3"]), deps=deps)

        assert "building 3" in words_repo.all()
        assert any("building 3" in reply for reply in update.effective_message.replies)

    async def test_delete_word_takes_the_whole_argument(self, deps, bot: FakeBot, words_repo):
        words_repo.add("building 3")
        update = make_update("/delete_word building 3", user_id=ADMIN_ID)
        await admin_handlers.delete_word(update, make_context(bot, ["building", "3"]), deps=deps)

        assert "building 3" not in words_repo.all()
        assert any("building 3" in reply for reply in update.effective_message.replies)

    async def test_delete_word_by_admin(self, deps, bot: FakeBot):
        deps.words.add("yard")
        update = make_update("/delete_word", user_id=ADMIN_ID)
        await admin_handlers.delete_word(update, make_context(bot, ["yard"]), deps=deps)
        assert deps.words.all() == frozenset()

    @pytest.mark.parametrize(
        "handler",
        [
            admin_handlers.start,
            admin_handlers.add_word,
            admin_handlers.delete_word,
            admin_handlers.list_words,
        ],
    )
    async def test_update_without_message_is_ignored(self, deps, bot: FakeBot, handler):
        update = FakeUpdate(
            effective_message=None,
            effective_chat=FakeChat(CHAT_ID),
            effective_user=FakeUser(id=ADMIN_ID),
        )
        await handler(update, make_context(bot, ["yard"]), deps=deps)

        assert bot.sent == []

    async def test_delete_word_by_stranger_is_refused(self, deps, bot: FakeBot):
        update = make_update("/delete_word yard", user_id=STRANGER_ID)
        await admin_handlers.delete_word(update, make_context(bot, ["yard"]), deps=deps)

        assert update.effective_message.replies == [deps.settings.not_admin_reply]

    async def test_admin_notification_failure_does_not_lose_the_word(
        self, settings, words_repo: WordRepository, chat_settings_repo, recent_posts_repo
    ):
        bot = FakeBot(fail_sending_to={300})
        wider = replace(settings, admin_ids=frozenset({ADMIN_ID, 300}))
        deps = make_deps(wider, words_repo, chat_settings_repo, recent_posts_repo)
        update = make_update("/add", user_id=ADMIN_ID, username="boss")

        await admin_handlers.add_word(update, make_context(bot, ["yard"]), deps=deps)

        assert deps.words.all() == frozenset({"yard"})

    async def test_list_words_by_stranger_is_refused(self, deps, bot: FakeBot):
        update = make_update("/list_words", user_id=STRANGER_ID)
        await admin_handlers.list_words(update, make_context(bot), deps=deps)
        assert update.effective_message.replies == [deps.settings.not_admin_reply]

    async def test_list_words_splits_into_several_messages(
        self, settings, words_repo: WordRepository, chat_settings_repo, recent_posts_repo
    ):
        bot = FakeBot()
        deps = make_deps(settings, words_repo, chat_settings_repo, recent_posts_repo)
        for index in range(2000):
            words_repo.add(f"word-{index:04d}")
        update = make_update("/list_words", user_id=ADMIN_ID)

        await admin_handlers.list_words(update, make_context(bot), deps=deps)

        replies = update.effective_message.replies
        assert len(replies) > 1
        assert all(len(chunk) <= 4096 for chunk in replies)


class TestSilent:
    async def test_wrong_argument_shows_usage(self, deps, bot: FakeBot):
        update = make_update("/silent", user_id=ADMIN_ID)
        await silent_handlers.silent(update, make_context(bot, ["maybe"]), deps=deps)
        assert update.effective_message.replies == [deps.settings.silent_usage_reply]
        assert deps.chat_settings.is_silent(CHAT_ID) is False

    async def test_any_participant_can_toggle(self, deps, bot: FakeBot):
        update = make_update("/silent", user_id=STRANGER_ID)
        await silent_handlers.silent(update, make_context(bot, ["on"]), deps=deps)
        assert deps.chat_settings.is_silent(CHAT_ID) is True

    async def test_update_without_message_is_ignored(self, deps, bot: FakeBot):
        update = FakeUpdate(
            effective_message=None,
            effective_chat=FakeChat(CHAT_ID),
            effective_user=FakeUser(id=ADMIN_ID),
        )
        await silent_handlers.silent(update, make_context(bot, ["on"]), deps=deps)

        assert bot.sent == []

    async def test_turns_silent_on(self, deps, bot: FakeBot):
        update = make_update("/silent", user_id=STRANGER_ID)
        await silent_handlers.silent(update, make_context(bot, ["ON"]), deps=deps)
        assert deps.chat_settings.is_silent(CHAT_ID) is True
        assert update.effective_message.replies == [deps.settings.silent_on_reply]

    async def test_turning_off(self, deps, bot: FakeBot):
        deps.chat_settings.set_silent(CHAT_ID, True)
        update = make_update("/silent", user_id=STRANGER_ID)
        await silent_handlers.silent(update, make_context(bot, ["off"]), deps=deps)
        assert deps.chat_settings.is_silent(CHAT_ID) is False
        assert update.effective_message.replies == [deps.settings.silent_off_reply]


class TestMessageHandler:
    async def test_disallowed_message_triggers_deletion(self, deps, bot: FakeBot):
        update = make_update(BAD_TEXT, message_id=42, user_id=STRANGER_ID, username="vasya")
        await message_handlers.on_message(update, make_context(bot), deps=deps)
        assert bot.deleted == [(CHAT_ID, 42)]
        assert (CHAT_ID, deps.settings.on_delete_reply, ()) in bot.sent

    async def test_allowed_message_is_left_alone(self, deps, bot: FakeBot):
        deps.words.add("garage")
        update = make_update(BAD_TEXT, user_id=STRANGER_ID)
        await message_handlers.on_message(update, make_context(bot), deps=deps)
        assert bot.deleted == []
        assert bot.sent == []

    async def test_update_without_message_is_ignored(self, deps, bot: FakeBot):
        update = make_update("text", user_id=STRANGER_ID)
        update.effective_message = None
        await message_handlers.on_message(update, make_context(bot), deps=deps)
        assert bot.deleted == []


class TestFromUpdateWithRealTelegramObjects:
    """from_update must work on real PTB objects too, not only on fakes."""

    def test_plain_message(self):
        from telegram import Chat, Message, Update, User

        message = Message(
            message_id=5,
            date=datetime.now(UTC),
            chat=Chat(id=CHAT_ID, type="group"),
            text="flooded yard",
            from_user=User(id=STRANGER_ID, first_name="Vasya", username="vasya", is_bot=False),
        )
        incoming = from_update(Update(update_id=1, message=message))
        assert incoming is not None
        assert (incoming.chat_id, incoming.message_id, incoming.user_label) == (
            CHAT_ID,
            5,
            "vasya",
        )
        assert incoming.is_reply is False

    def test_message_without_user_and_text(self):
        from telegram import Chat, Message, Update

        message = Message(
            message_id=6,
            date=datetime.now(UTC),
            chat=Chat(id=CHAT_ID, type="channel"),
        )
        incoming = from_update(Update(update_id=2, message=message))
        assert incoming is not None
        assert incoming.text is None
        assert incoming.user_id is None
        assert incoming.user_label == "anonymous"


@pytest.mark.parametrize("command", ["add_word", "delete_word", "list_words", "start"])
def test_admin_commands_are_registered(command):
    assert hasattr(admin_handlers, command)


@pytest.mark.parametrize(
    "module",
    [admin_handlers, silent_handlers, message_handlers, ban_handlers, delete_handlers],
)
def test_every_handler_module_exposes_register(module):
    assert callable(module.register)
