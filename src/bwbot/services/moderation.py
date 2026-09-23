"""Сервис модерации: решает судьбу сообщения и выполняет действие."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from bwbot.callbacks import BanTarget, DeleteTarget, ban_button, delete_button
from bwbot.config import Settings
from bwbot.dedupe import find_repeat
from bwbot.moderation import Action, Decision, decide
from bwbot.services.api import ApiError, Button, ChatApi, notify_all
from bwbot.storage.chat_settings import ChatSettingsRepository
from bwbot.storage.recent_posts import RecentPostsRepository
from bwbot.storage.words import WordRepository
from bwbot.utils import TELEGRAM_MESSAGE_LIMIT, clip, human_age

logger = logging.getLogger(__name__)

# Сколько текста нарушителя попадает в отчёт. Остальное место нужно шапке,
# пометке о действиях администратора и кнопке — иначе Telegram отклонит
# сообщение, и администраторы не узнают об удалении вовсе.
REPORT_TEXT_BUDGET = 3000


@dataclass(frozen=True)
class ModerationService:
    settings: Settings
    words: WordRepository
    chat_settings: ChatSettingsRepository
    recent_posts: RecentPostsRepository
    # Часы отдельным полем, чтобы окно повторов тестировалось без махинаций со временем.
    clock: Callable[[], float] = field(default=time.time)

    async def handle_message(
        self,
        api: ChatApi,
        *,
        chat_id: int,
        message_id: int,
        text: str | None,
        is_reply: bool = False,
        user_label: str = "неизвестный",
        user_id: int | None = None,
    ) -> Decision:
        decision = decide(
            text,
            allowed_words=self.words.all(),
            min_length=self.settings.min_length,
            is_reply=is_reply,
        )
        if not decision.deletes:
            if decision.action is Action.ALLOW and user_id is not None:
                await self._report_repeat(
                    api,
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text or "",
                    user_label=user_label,
                    user_id=user_id,
                )
            return decision

        try:
            await api.delete_message(chat_id, message_id)
        except ApiError as exc:
            # Без прав на удаление бот бессилен, но молчать хуже, чем сказать.
            logger.error("не удалось удалить сообщение %s в чате %s: %s", message_id, chat_id, exc)
            await self._notify_admins(
                api, f"Не удалось удалить сообщение {message_id} в чате {chat_id}: {exc}"
            )
            return decision

        if not self.chat_settings.is_silent(chat_id):
            await api.send_message(chat_id, self.settings.on_delete_reply)

        report = f"Удалено в чате {chat_id} от {user_label}: {clip(text or '', REPORT_TEXT_BUDGET)}"
        logger.info(report)
        # Кнопка есть только если знаем, кого банить: у анонимных постов канала
        # автора нет, и банить некого. Администраторов — получателей отчёта — кнопка
        # не предлагает вовсе: банить своих нельзя.
        buttons: tuple[Button, ...] = ()
        if user_id is not None and not self.settings.is_admin(user_id):
            target = BanTarget(chat_id=chat_id, user_id=user_id)
            buttons = (ban_button(target, self.settings.ban_button_label),)
        await self._notify_admins(api, report, buttons)
        return decision

    async def _notify_admins(
        self, api: ChatApi, text: str, buttons: tuple[Button, ...] = ()
    ) -> None:
        failures = await notify_all(api, self.settings.admin_ids, text, buttons)
        for failure in failures:
            logger.warning("Не удалось уведомить администраторов: %s", failure)

    async def _report_repeat(
        self,
        api: ChatApi,
        *,
        chat_id: int,
        message_id: int,
        text: str,
        user_label: str,
        user_id: int,
    ) -> None:
        """Оставленное сообщение идёт в базу сравнения, а его копия — администраторам.

        Сам повтор не удаляем: порог похожести подстраховки не даёт молча
        стирать живые объявления, решение остаётся за администратором.
        """
        now = self.clock()
        repeat = find_repeat(
            self.recent_posts.posts(chat_id, user_id),
            text,
            now=now,
            window_days=self.settings.dup_window_days,
            threshold=self.settings.dup_threshold,
        )
        self.recent_posts.record(chat_id, user_id, message_id, text, at=now)
        if repeat is None:
            return

        report = clip(
            self.settings.dup_report.format(
                chat_id=chat_id,
                user_label=user_label,
                text=clip(text, REPORT_TEXT_BUDGET),
                matched_age=human_age(repeat.posted_at, now),
                score=round(repeat.score * 100),
            ),
            TELEGRAM_MESSAGE_LIMIT,
        )
        logger.info(
            "repeat suspected: chat=%s user=%s message=%s matched=%s score=%.2f",
            chat_id,
            user_id,
            message_id,
            repeat.message_id,
            repeat.score,
        )
        target = DeleteTarget(chat_id=chat_id, message_id=message_id)
        buttons = (delete_button(target, self.settings.dup_delete_label),)
        await self._notify_admins(api, report, buttons)
