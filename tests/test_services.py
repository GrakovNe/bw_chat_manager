"""Тесты сервисного слоя на фейковом Bot API."""

from __future__ import annotations

import pytest

from bwbot.config import Settings
from bwbot.moderation import Action
from bwbot.services.admin import WordAdminService
from bwbot.services.api import notify_all
from bwbot.services.moderation import ModerationService
from bwbot.storage.words import WordRepository
from bwbot.telegram_api import TelegramApi
from bwbot.utils import TELEGRAM_MESSAGE_LIMIT
from conftest import ADMIN_ID, CHAT_ID, STRANGER_ID, FakeBot

BAD_TEXT = "продам гараж в другом жк"
GOOD_TEXT = "затопило двор у корпуса 1"


class TestModerationService:
    async def test_allowed_message_changes_nothing(self, deps, api, bot: FakeBot):
        deps.words.add("двор")
        decision = await deps.moderation.handle_message(
            api, chat_id=CHAT_ID, message_id=1, text=GOOD_TEXT
        )
        assert decision.action is Action.ALLOW
        assert bot.deleted == []
        assert bot.sent == []

    async def test_short_message_changes_nothing(self, deps, api, bot: FakeBot):
        decision = await deps.moderation.handle_message(
            api, chat_id=CHAT_ID, message_id=1, text="ок"
        )
        assert decision.action is Action.IGNORE_SHORT
        assert bot.deleted == []
        assert bot.sent == []

    async def test_reply_is_never_touched(self, deps, api, bot: FakeBot):
        decision = await deps.moderation.handle_message(
            api, chat_id=CHAT_ID, message_id=1, text=BAD_TEXT, is_reply=True
        )
        assert decision.action is Action.IGNORE_REPLY
        assert bot.deleted == []

    async def test_disallowed_message_is_deleted_and_everyone_notified(
        self, deps, api, bot: FakeBot
    ):
        decision = await deps.moderation.handle_message(
            api,
            chat_id=CHAT_ID,
            message_id=7,
            text=BAD_TEXT,
            user_label="vasya",
        )
        assert decision.action is Action.DELETE
        assert bot.deleted == [(CHAT_ID, 7)]
        assert (CHAT_ID, deps.settings.on_delete_reply, ()) in bot.sent
        reports = [text for chat_id, text, _ in bot.sent if chat_id == ADMIN_ID]
        assert len(reports) == 1
        assert "vasya" in reports[0]
        assert BAD_TEXT in reports[0]

    async def test_silent_mode_skips_chat_reply_but_not_admin_report(self, deps, api, bot: FakeBot):
        deps.chat_settings.set_silent(CHAT_ID, True)
        await deps.moderation.handle_message(
            api, chat_id=CHAT_ID, message_id=7, text=BAD_TEXT, user_label="vasya"
        )
        assert bot.deleted == [(CHAT_ID, 7)]
        assert [chat_id for chat_id, _, _ in bot.sent] == [ADMIN_ID]

    async def test_admin_report_carries_ban_button(self, deps, api, bot: FakeBot):
        await deps.moderation.handle_message(
            api,
            chat_id=CHAT_ID,
            message_id=7,
            text=BAD_TEXT,
            user_label="vasya",
            user_id=STRANGER_ID,
        )
        label = deps.settings.ban_button_label
        reports = [buttons for chat_id, _, buttons in bot.sent if chat_id == ADMIN_ID]
        assert reports == [((label, f"ban:{CHAT_ID}:{STRANGER_ID}"),)]

    async def test_report_about_admin_has_no_button(self, deps, api, bot: FakeBot):
        await deps.moderation.handle_message(
            api,
            chat_id=CHAT_ID,
            message_id=7,
            text=BAD_TEXT,
            user_label="boss",
            user_id=ADMIN_ID,
        )
        reports = [buttons for chat_id, _, buttons in bot.sent if chat_id == ADMIN_ID]
        assert reports == [()]

    async def test_report_without_known_author_has_no_button(self, deps, api, bot: FakeBot):
        await deps.moderation.handle_message(
            api, chat_id=CHAT_ID, message_id=7, text=BAD_TEXT, user_label="аноним"
        )
        reports = [buttons for chat_id, _, buttons in bot.sent if chat_id == ADMIN_ID]
        assert reports == [()]

    async def test_chat_reply_never_carries_the_button(self, deps, api, bot: FakeBot):
        await deps.moderation.handle_message(
            api, chat_id=CHAT_ID, message_id=7, text=BAD_TEXT, user_id=STRANGER_ID
        )
        in_chat = [buttons for chat_id, _, buttons in bot.sent if chat_id == CHAT_ID]
        assert in_chat == [()]

    async def test_admin_notification_failure_does_not_break_handling(
        self,
        settings: Settings,
        words_repo: WordRepository,
        chat_settings_repo,
        recent_posts_repo,
    ):
        bot = FakeBot(fail_sending_to={ADMIN_ID})
        service = ModerationService(settings, words_repo, chat_settings_repo, recent_posts_repo)
        decision = await service.handle_message(
            TelegramApi(bot), chat_id=CHAT_ID, message_id=7, text=BAD_TEXT
        )
        assert decision.action is Action.DELETE
        assert bot.deleted == [(CHAT_ID, 7)]
        assert (CHAT_ID, settings.on_delete_reply, ()) in bot.sent


class TestWordAdminService:
    def test_add_ok(self, words_repo: WordRepository):
        result = WordAdminService(words_repo).add_word("  Корпус-3 ")
        assert result.ok is True
        assert words_repo.all() == frozenset({"корпус-3"})

    def test_add_without_argument_shows_usage(self, words_repo: WordRepository):
        result = WordAdminService(words_repo).add_word(None)
        assert result.ok is False
        assert "/add" in result.message

    def test_delete_without_argument_shows_usage(self, words_repo: WordRepository):
        result = WordAdminService(words_repo).delete_word(None)
        assert result.ok is False
        assert "/delete_word" in result.message

    def test_add_duplicate(self, words_repo: WordRepository):
        service = WordAdminService(words_repo)
        assert service.add_word("двор").ok is True
        assert service.add_word("ДВОР").ok is False

    def test_delete_ok_and_missing(self, words_repo: WordRepository):
        service = WordAdminService(words_repo)
        service.add_word("двор")
        assert service.delete_word("двор").ok is True
        assert service.delete_word("двор").ok is False

    def test_list_empty(self, words_repo: WordRepository):
        result = WordAdminService(words_repo).list_words()
        assert result.ok is True
        assert result.extra_chunks == ()

    def test_list_is_numbered_and_sorted(self, words_repo: WordRepository):
        words_repo.add("б")
        words_repo.add("а")
        result = WordAdminService(words_repo).list_words()
        assert result.message.startswith("Разрешённые слова (2):")
        assert result.message.splitlines()[1:] == ["а", "б"]


async def test_notify_all_swallows_partial_failures():
    bot = FakeBot(fail_sending_to={ADMIN_ID})
    failures = await notify_all(TelegramApi(bot), [ADMIN_ID, 300], "привет")
    assert len(failures) == 1
    assert bot.sent == [(300, "привет", ())]


@pytest.mark.parametrize("word", ["", None])
def test_add_word_rejects_blank(word, words_repo: WordRepository):
    assert WordAdminService(words_repo).add_word(word).ok is False


class TestDeleteFailure:
    async def test_failed_delete_is_reported_to_admins(self, deps, api, bot: FakeBot):
        """Бот без прав на удаление бессилен, но молчать об этом не должен."""
        bot.fail_deleting = (CHAT_ID, 7)
        decision = await deps.moderation.handle_message(
            api,
            chat_id=CHAT_ID,
            message_id=7,
            text=BAD_TEXT,
            user_label="vasya",
            user_id=STRANGER_ID,
        )
        assert decision.action is Action.DELETE
        assert bot.deleted == []
        reports = [text for chat_id, text, _ in bot.sent if chat_id == ADMIN_ID]
        assert len(reports) == 1
        assert "Не удалось удалить" in reports[0]
        assert "message to delete not found" in reports[0]

    async def test_failed_delete_does_not_answer_in_the_chat(self, deps, api, bot: FakeBot):
        bot.fail_deleting = (CHAT_ID, 7)
        await deps.moderation.handle_message(
            api, chat_id=CHAT_ID, message_id=7, text=BAD_TEXT, user_label="vasya"
        )
        assert (CHAT_ID, deps.settings.on_delete_reply, ()) not in bot.sent

    async def test_failed_delete_is_not_offered_for_banning(self, deps, api, bot: FakeBot):
        bot.fail_deleting = (CHAT_ID, 7)
        await deps.moderation.handle_message(
            api,
            chat_id=CHAT_ID,
            message_id=7,
            text=BAD_TEXT,
            user_label="vasya",
            user_id=STRANGER_ID,
        )
        assert all(buttons == () for _, _, buttons in bot.sent)


class TestReportLength:
    async def test_huge_message_is_clipped_into_one_report(self, deps, api, bot: FakeBot):
        await deps.moderation.handle_message(
            api,
            chat_id=CHAT_ID,
            message_id=7,
            text="гараж " * 1200,
            user_label="vasya",
        )
        reports = [text for chat_id, text, _ in bot.sent if chat_id == ADMIN_ID]
        assert len(reports) == 1
        assert len(reports[0]) <= TELEGRAM_MESSAGE_LIMIT
        assert reports[0].endswith("…")


class TestLinkPreviews:
    async def test_outgoing_messages_have_previews_disabled(self, deps, api, bot: FakeBot):
        await deps.moderation.handle_message(
            api,
            chat_id=CHAT_ID,
            message_id=7,
            text="продам гараж https://example.com",
            user_label="vasya",
        )
        assert bot.sent
        assert all(options is not None and options.is_disabled for options in bot.previews)
