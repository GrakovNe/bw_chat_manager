"""Фейки вместо Telegram: тесты не должны ходить в сеть."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from bwbot.config import Settings
from bwbot.deps import Deps
from bwbot.services.admin import WordAdminService
from bwbot.services.moderation import ModerationService
from bwbot.storage.chat_settings import ChatSettingsRepository
from bwbot.storage.words import WordRepository

ADMIN_ID = 100
STRANGER_ID = 200
CHAT_ID = -1001


class FakeBot:
    """Записывает вызовы Bot API вместо реальных запросов."""

    def __init__(self, fail_sending_to: set[int] | None = None) -> None:
        self.sent: list[tuple[int, str]] = []
        self.deleted: list[tuple[int, int]] = []
        self.fail_sending_to = fail_sending_to or set()

    async def send_message(self, chat_id: int | None = None, text: str | None = None) -> None:
        if chat_id in self.fail_sending_to:
            raise RuntimeError(f"нет доступа в чат {chat_id}")
        self.sent.append((chat_id, text))

    async def delete_message(
        self, chat_id: int | None = None, message_id: int | None = None
    ) -> None:
        self.deleted.append((chat_id, message_id))


@dataclass
class FakeMessage:
    message_id: int = 10
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
        text=text,
        reply_to_message=FakeMessage(message_id=1) if is_reply else None,
    )
    user = (
        FakeUser(id=user_id, username=username, full_name=username or "Аноним") if user_id else None
    )
    return FakeUpdate(
        effective_message=message, effective_chat=FakeChat(chat_id), effective_user=user
    )


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
    )


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()
