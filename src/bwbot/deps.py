"""Зависимости, которые внедряются в хендлеры."""

from __future__ import annotations

from dataclasses import dataclass

from bwbot.config import ConfigError, Settings
from bwbot.services.admin import WordAdminService
from bwbot.services.moderation import ModerationService
from bwbot.storage.chat_settings import ChatSettingsRepository
from bwbot.storage.words import WordRepository


@dataclass
class Deps:
    settings: Settings
    words: WordRepository
    chat_settings: ChatSettingsRepository
    moderation: ModerationService
    word_admin: WordAdminService

    @classmethod
    def build(cls, settings: Settings) -> Deps:
        if not settings.words_file.exists():
            raise ConfigError(
                f"Нет файла слов: {settings.words_file}. "
                "Создайте его (одно слово в строке) или укажите DATA_DIR."
            )
        words = WordRepository(settings.words_file)
        chat_settings = ChatSettingsRepository(settings.chat_settings_file)
        return cls(
            settings=settings,
            words=words,
            chat_settings=chat_settings,
            moderation=ModerationService(settings, words, chat_settings),
            word_admin=WordAdminService(words),
        )
