"""Фейки вместо Telegram: тесты не должны ходить в сеть."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from telegram.error import Forbidden

from bwbot.config import Settings
from bwbot.deps import Deps
from bwbot.services.admin import WordAdminService
from bwbot.services.api import Button, ChatApi
from bwbot.services.bans import BanService
from bwbot.services.moderation import ModerationService
from bwbot.storage.chat_settings import ChatSettingsRepository
from bwbot.storage.words import WordRepository
from bwbot.telegram_api import TelegramApi

ADMIN_ID = 100
STRANGER_ID = 200
CHAT_ID = -1001


def _buttons(reply_markup: object | None) -> tuple[Button, ...]:
    """Достаёт кнопки из настоящего InlineKeyboardMarkup, который собрал TelegramApi."""
    rows = getattr(reply_markup, "inline_keyboard", None) or ()
    return tuple((button.text, button.callback_data) for row in rows for button in row)


class FakeBot:
    """Подмена telegram.Bot: записывает вызовы вместо реальных запросов.

    Методы повторяют имена и сигнатуры настоящего Bot, поэтому тесты проходят
    через настоящий TelegramApi и проверяют в том числе сборку разметки.
    """

    def __init__(
        self,
        fail_sending_to: set[int] | None = None,
        fail_banning: tuple[int, int] | None = None,
        ban_error: str = "Forbidden: bot can't ban chat administrators",
    ) -> None:
        self.sent: list[tuple[int, str, tuple[Button, ...]]] = []
        self.deleted: list[tuple[int, int]] = []
        self.edited: list[tuple[int, int, str, tuple[Button, ...]]] = []
        self.answers: list[tuple[str, str]] = []
        self.banned: list[tuple[int, int]] = []
        self.fail_sending_to = fail_sending_to or set()
        self.fail_banning = fail_banning
        self.ban_error = ban_error

    async def send_message(
        self,
        chat_id: int | None = None,
        text: str | None = None,
        reply_markup: object | None = None,
    ) -> None:
        if chat_id in self.fail_sending_to:
            raise RuntimeError(f"нет доступа в чат {chat_id}")
        self.sent.append((chat_id, text, _buttons(reply_markup)))

    async def delete_message(
        self, chat_id: int | None = None, message_id: int | None = None
    ) -> None:
        self.deleted.append((chat_id, message_id))

    async def edit_message_text(
        self,
        chat_id: int | None = None,
        message_id: int | None = None,
        text: str | None = None,
        reply_markup: object | None = None,
    ) -> None:
        self.edited.append((chat_id, message_id, text, _buttons(reply_markup)))

    async def answer_callback_query(
        self, callback_query_id: str | None = None, text: str | None = None
    ) -> None:
        self.answers.append((callback_query_id, text))

    async def ban_chat_member(self, chat_id: int | None = None, user_id: int | None = None) -> None:
        if self.fail_banning == (chat_id, user_id):
            raise Forbidden(self.ban_error)
        self.banned.append((chat_id, user_id))


@dataclass
class FakeMessage:
    message_id: int = 10
    chat_id: int = CHAT_ID
    text: str | None = None
    reply_to_message: object | None = None
    replies: list[str] = field(default_factory=list)

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


@dataclass
class FakeChat:
    id: int = CHAT_ID


@dataclass
class FakeUser:
    id: int = STRANGER_ID
    username: str | None = "stranger"
    full_name: str = "Stranger"


@dataclass
class FakeUpdate:
    effective_message: FakeMessage | None
    effective_chat: FakeChat | None
    effective_user: FakeUser | None


@dataclass
class FakeCallbackQuery:
    id: str = "cb-1"
    data: str | None = None
    from_user: FakeUser | None = None
    message: FakeMessage | None = None


@dataclass
class FakeCallbackUpdate:
    callback_query: FakeCallbackQuery | None


def make_update(
    text: str | None = "короткое",
    *,
    chat_id: int = CHAT_ID,
    message_id: int = 10,
    user_id: int | None = STRANGER_ID,
    username: str | None = "stranger",
    is_reply: bool = False,
) -> FakeUpdate:
    message = FakeMessage(
        message_id=message_id,
        chat_id=chat_id,
        text=text,
        reply_to_message=FakeMessage(message_id=1) if is_reply else None,
    )
    user = (
        FakeUser(id=user_id, username=username, full_name=username or "Аноним") if user_id else None
    )
    return FakeUpdate(
        effective_message=message, effective_chat=FakeChat(chat_id), effective_user=user
    )


def make_callback(
    data: str | None,
    *,
    by_id: int | None = ADMIN_ID,
    username: str | None = "boss",
    callback_id: str = "cb-1",
    report: FakeMessage | None = None,
) -> FakeCallbackUpdate:
    """Нажатие кнопки под отчётом об удалении."""
    message = report if report is not None else FakeMessage(message_id=42, text="Удалено: ляляля")
    user = FakeUser(id=by_id, username=username, full_name=username or "Аноним") if by_id else None
    return FakeCallbackUpdate(callback_query=FakeCallbackQuery(callback_id, data, user, message))


def make_context(bot: FakeBot, args: list[str] | None = None) -> Any:
    return SimpleNamespace(bot=bot, args=args)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        token="fake:token",
        min_length=10,
        admin_ids=frozenset({ADMIN_ID}),
        data_dir=tmp_path,
    )


@pytest.fixture
def words_repo(settings: Settings) -> WordRepository:
    settings.words_file.write_text("", encoding="utf-8")
    return WordRepository(settings.words_file)


@pytest.fixture
def chat_settings_repo(settings: Settings) -> ChatSettingsRepository:
    return ChatSettingsRepository(settings.chat_settings_file)


@pytest.fixture
def deps(settings: Settings, words_repo: WordRepository, chat_settings_repo) -> Deps:
    return Deps(
        settings=settings,
        words=words_repo,
        chat_settings=chat_settings_repo,
        moderation=ModerationService(settings, words_repo, chat_settings_repo),
        word_admin=WordAdminService(words_repo),
        bans=BanService(settings),
    )


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
def api(bot: FakeBot) -> ChatApi:
    """Настоящий адаптер поверх фейкового Bot."""
    return TelegramApi(bot)
