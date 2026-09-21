"""Тесты хендлеров: только Telegram-обвязка, логика проверена отдельно."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from bwbot.config import Settings
from bwbot.deps import Deps
from bwbot.handlers import admin as admin_handlers
from bwbot.handlers import messages as message_handlers
from bwbot.handlers import silent as silent_handlers
from bwbot.handlers.extract import from_update
from bwbot.services.admin import WordAdminService
from bwbot.services.moderation import ModerationService
from bwbot.storage.words import WordRepository
from conftest import ADMIN_ID, CHAT_ID, STRANGER_ID, FakeBot, make_context, make_update

BAD_TEXT = "продам гараж в другом жк"


def make_deps(settings: Settings, words_repo: WordRepository, chat_settings_repo) -> Deps:
    return Deps(
        settings=settings,
        words=words_repo,
        chat_settings=chat_settings_repo,
        moderation=ModerationService(settings, words_repo, chat_settings_repo),
        word_admin=WordAdminService(words_repo),
    )


class TestAdminCommands:
    async def test_start_answers(self, deps, bot: FakeBot):
        update = make_update("/start", user_id=ADMIN_ID)
        await admin_handlers.start(update, make_context(bot), deps=deps)
        assert update.effective_message.replies == [admin_handlers.START_TEXT]

    async def test_add_by_stranger_is_refused(self, deps, bot: FakeBot):
        update = make_update("/add", user_id=STRANGER_ID)
        await admin_handlers.add_word(update, make_context(bot, ["корпус 5"]), deps=deps)
        assert update.effective_message.replies == [deps.settings.not_admin_reply]
        assert deps.words.all() == frozenset()
        assert bot.sent == []

    async def test_add_by_admin_writes_file_and_replies(self, deps, bot: FakeBot):
        update = make_update("/add", user_id=ADMIN_ID, username="boss")
        await admin_handlers.add_word(update, make_context(bot, [" Корпус 5 "]), deps=deps)
        assert deps.words.all() == frozenset({"корпус 5"})
        assert "корпус 5" in update.effective_message.replies[0]

    async def test_add_notifies_other_admins_only(
        self, settings, words_repo: WordRepository, chat_settings_repo
    ):
        bot = FakeBot()
        wider = replace(settings, admin_ids=frozenset({ADMIN_ID, 300}))
        deps = make_deps(wider, words_repo, chat_settings_repo)
        update = make_update("/add", user_id=ADMIN_ID, username="boss")

        await admin_handlers.add_word(update, make_context(bot, ["двор"]), deps=deps)

        assert [chat_id for chat_id, _ in bot.sent] == [300]
        assert "boss" in bot.sent[0][1]
        assert "двор" in bot.sent[0][1]

    async def test_add_without_argument_shows_usage(self, deps, bot: FakeBot):
        update = make_update("/add", user_id=ADMIN_ID)
        await admin_handlers.add_word(update, make_context(bot, []), deps=deps)
        assert "/add" in update.effective_message.replies[0]
        assert deps.words.all() == frozenset()

    async def test_delete_word_by_admin(self, deps, bot: FakeBot):
        deps.words.add("двор")
        update = make_update("/delete_word", user_id=ADMIN_ID)
        await admin_handlers.delete_word(update, make_context(bot, ["двор"]), deps=deps)
        assert deps.words.all() == frozenset()

    async def test_list_words_by_stranger_is_refused(self, deps, bot: FakeBot):
        update = make_update("/list_words", user_id=STRANGER_ID)
        await admin_handlers.list_words(update, make_context(bot), deps=deps)
        assert update.effective_message.replies == [deps.settings.not_admin_reply]

    async def test_list_words_splits_into_several_messages(
        self, settings, words_repo: WordRepository, chat_settings_repo
    ):
        bot = FakeBot()
        deps = make_deps(settings, words_repo, chat_settings_repo)
        for index in range(2000):
            words_repo.add(f"словo-{index:04d}")
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
        assert (CHAT_ID, deps.settings.on_delete_reply) in bot.sent

    async def test_allowed_message_is_left_alone(self, deps, bot: FakeBot):
        deps.words.add("гараж")
        update = make_update(BAD_TEXT, user_id=STRANGER_ID)
        await message_handlers.on_message(update, make_context(bot), deps=deps)
        assert bot.deleted == []
        assert bot.sent == []

    async def test_update_without_message_is_ignored(self, deps, bot: FakeBot):
        update = make_update("текст", user_id=STRANGER_ID)
        update.effective_message = None
        await message_handlers.on_message(update, make_context(bot), deps=deps)
        assert bot.deleted == []


class TestFromUpdateWithRealTelegramObjects:
    """from_update должен работать и на настоящих объектах PTB, а не только на фейках."""

    def test_plain_message(self):
        from telegram import Chat, Message, Update, User

        message = Message(
            message_id=5,
            date=datetime.now(UTC),
            chat=Chat(id=CHAT_ID, type="group"),
            text="затопило двор",
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
        assert incoming.user_label == "аноним"


@pytest.mark.parametrize("command", ["add_word", "delete_word", "list_words", "start"])
def test_admin_commands_are_registered(command):
    assert hasattr(admin_handlers, command)
