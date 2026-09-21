"""Сервис модерации: решает судьбу сообщения и выполняет действие."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from bwbot.config import Settings
from bwbot.moderation import Decision, decide
from bwbot.services.api import ChatApi, notify_all
from bwbot.storage.chat_settings import ChatSettingsRepository
from bwbot.storage.words import WordRepository

logger = logging.getLogger(__name__)


@dataclass
class ModerationService:
    settings: Settings
    words: WordRepository
    chat_settings: ChatSettingsRepository

    async def handle_message(
        self,
        api: ChatApi,
        *,
        chat_id: int,
        message_id: int,
        text: str | None,
        is_reply: bool = False,
        user_label: str = "неизвестный",
    ) -> Decision:
        decision = decide(
            text,
            allowed_words=self.words.all(),
            min_length=self.settings.min_length,
            is_reply=is_reply,
        )
        if not decision.deletes:
            return decision

        await api.delete_message(chat_id, message_id)

        if not self.chat_settings.is_silent(chat_id):
            await api.send_message(chat_id, self.settings.on_delete_reply)

        report = f"Удалено в чате {chat_id} от {user_label}: {text}"
        logger.info(report)
        failures = await notify_all(api, self.settings.admin_ids, report)
        for failure in failures:
            logger.warning("Не удалось уведомить администраторов: %s", failure)

        return decision
