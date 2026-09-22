"""Зависимости, которые внедряются в хендлеры."""

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


@dataclass
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
                f"Нет файла слов: {settings.words_file}. "
                "Создайте его (одно слово в строке) или укажите DATA_DIR."
            )
        words = WordRepository(settings.words_file)
        chat_settings = ChatSettingsRepository(settings.chat_settings_file)
        migrated = chat_settings.migrate()
        if migrated:
            logging.getLogger(__name__).info(
                "Перенесли тихий режим из старого формата: %s чат(ов)", migrated
            )
        recent_posts = RecentPostsRepository(
            settings.recent_posts_file, window_days=settings.dup_window_days
        )
        return cls(
            settings=settings,
            words=words,
            chat_settings=chat_settings,
            moderation=ModerationService(settings, words, chat_settings, recent_posts),
            word_admin=WordAdminService(words),
            bans=BanService(settings),
            deletes=DeleteService(settings),
        )
