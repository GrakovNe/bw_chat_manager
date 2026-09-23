"""Dependencies injected into the handlers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from bwbot.config import ConfigError, Settings
from bwbot.services.admin import WordAdminService
from bwbot.services.bans import BanService
from bwbot.services.deletes import DeleteService
from bwbot.services.moderation import ModerationService
from bwbot.storage.chat_settings import ChatSettingsRepository
from bwbot.storage.recent_posts import RecentPostsRepository
from bwbot.storage.words import WordRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Deps:
    settings: Settings
    words: WordRepository
    chat_settings: ChatSettingsRepository
    moderation: ModerationService
    word_admin: WordAdminService
    bans: BanService
    deletes: DeleteService

    @classmethod
    def build(cls, settings: Settings) -> Deps:
        if not settings.words_file.exists():
            raise ConfigError(
                f"No words file: {settings.words_file}. "
                "Create it (one word per line) or point DATA_DIR to it."
            )
        words = WordRepository(settings.words_file)
        chat_settings = ChatSettingsRepository(settings.chat_settings_file)
        migrated = chat_settings.migrate()
        if migrated:
            logger.info("Migrated silent mode from the old format: %s chat(s)", migrated)
        recent_posts = RecentPostsRepository(
            settings.recent_posts_file, window_days=settings.dup_window_days
        )
        # The window may have gone stale while the bot was down: clean up right
        # away, otherwise the file grows with messages nobody will remember.
        stale = recent_posts.prune()
        if stale:
            logger.info("Forgot %s stale repeat messages", stale)
        return cls(
            settings=settings,
            words=words,
            chat_settings=chat_settings,
            moderation=ModerationService(settings, words, chat_settings, recent_posts),
            word_admin=WordAdminService(words),
            bans=BanService(settings),
            deletes=DeleteService(settings),
        )
