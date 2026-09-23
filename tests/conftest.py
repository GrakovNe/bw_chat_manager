"""Fakes instead of Telegram: tests must not hit the network."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from telegram.error import BadRequest, Forbidden

from bwbot.config import Settings
from bwbot.deps import Deps
from bwbot.services.admin import WordAdminService
from bwbot.services.api import Button, ChatApi
from bwbot.services.bans import BanService
from bwbot.services.deletes import DeleteService
from bwbot.services.moderation import ModerationService
from bwbot.storage.chat_settings import ChatSettingsRepository
from bwbot.storage.recent_posts import RecentPostsRepository
from bwbot.storage.words import WordRepository
from bwbot.telegram_api import TelegramApi

ADMIN_ID = 100
STRANGER_ID = 200
CHAT_ID = -1001


def _buttons(reply_markup: object | None) -> tuple[Button, ...]:
    """Extracts buttons from the real InlineKeyboardMarkup that TelegramApi built."""
    rows = getattr(reply_markup, "inline_keyboard", None) or ()
    return tuple((button.text, button.callback_data) for row in rows for button in row)


class FakeBot:
    """A stand-in for telegram.Bot: records calls instead of real requests.

    The methods repeat the real Bot's names and signatures, so tests go through
    the real TelegramApi and also check the markup assembly.
    """

    def __init__(
        self,
        fail_sending_to: set[int] | None = None,
        fail_banning: tuple[int, int] | None = None,
        ban_error: str = "Forbidden: bot can't ban chat administrators",
        fail_deleting: tuple[int, int] | None = None,
        delete_error: str = "BadRequest: message to delete not found",
        fail_editing: bool = False,
    ) -> None:
        self.sent: list[tuple[int, str, tuple[Button, ...]]] = []
        self.previews: list[object] = []
        self.deleted: list[tuple[int, int]] = []
        self.edited: list[tuple[int, int, str, tuple[Button, ...]]] = []
        self.answers: list[tuple[str, str]] = []
        self.banned: list[tuple[int, int]] = []
        self.fail_sending_to = fail_sending_to or set()
        self.fail_banning = fail_banning
        self.ban_error = ban_error
        self.fail_deleting = fail_deleting
        self.delete_error = delete_error
        self.fail_editing = fail_editing

    async def send_message(
        self,
        chat_id: int | None = None,
        text: str | None = None,
        reply_markup: object | None = None,
        link_preview_options: object | None = None,
    ) -> None:
        if chat_id in self.fail_sending_to:
            raise RuntimeError(f"no access to chat {chat_id}")
        self.sent.append((chat_id, text, _buttons(reply_markup)))
        self.previews.append(link_preview_options)

    async def delete_message(
        self, chat_id: int | None = None, message_id: int | None = None
    ) -> None:
        if self.fail_deleting == (chat_id, message_id):
            raise BadRequest(self.delete_error)
        self.deleted.append((chat_id, message_id))

    async def edit_message_text(
        self,
        chat_id: int | None = None,
        message_id: int | None = None,
        text: str | None = None,
        reply_markup: object | None = None,
    ) -> None:
        if self.fail_editing:
            raise BadRequest("message can't be edited")
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
    text: str | None = "short",
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
        FakeUser(id=user_id, username=username, full_name=username or "Anonymous")
        if user_id
        else None
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
    """A button press under a deletion report."""
    message = (
        report if report is not None else FakeMessage(message_id=42, text="Deleted: blah blah")
    )
    user = (
        FakeUser(id=by_id, username=username, full_name=username or "Anonymous") if by_id else None
    )
    return FakeCallbackUpdate(callback_query=FakeCallbackQuery(callback_id, data, user, message))


class FakeClock:
    """Time by the test clock: the repeat window and "N days ago" are checked statically."""

    def __init__(self, now: float = 1_700_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, *, days: float = 0.0, seconds: float = 0.0) -> None:
        self.now += days * 86400 + seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


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
def recent_posts_repo(settings: Settings) -> RecentPostsRepository:
    return RecentPostsRepository(settings.recent_posts_file, window_days=settings.dup_window_days)


@pytest.fixture
def deps(
    settings: Settings,
    words_repo: WordRepository,
    chat_settings_repo,
    recent_posts_repo,
    clock: FakeClock,
) -> Deps:
    return Deps(
        settings=settings,
        words=words_repo,
        chat_settings=chat_settings_repo,
        moderation=ModerationService(
            settings, words_repo, chat_settings_repo, recent_posts_repo, clock
        ),
        word_admin=WordAdminService(words_repo),
        bans=BanService(settings),
        deletes=DeleteService(settings),
    )


@pytest.fixture
def bot() -> FakeBot:
    return FakeBot()


@pytest.fixture
def api(bot: FakeBot) -> ChatApi:
    """The real adapter over a fake Bot."""
    return TelegramApi(bot)
