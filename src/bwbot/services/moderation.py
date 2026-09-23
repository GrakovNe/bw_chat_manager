"""Moderation service: decides a message's fate and performs the action."""

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

# How much of the offender's text goes into the report. The rest of the space is
# needed for the header, the note about the administrator's actions and the
# button — otherwise Telegram rejects the message and the administrators learn
# about the deletion not at all.
REPORT_TEXT_BUDGET = 3000


@dataclass(frozen=True)
class ModerationService:
    settings: Settings
    words: WordRepository
    chat_settings: ChatSettingsRepository
    recent_posts: RecentPostsRepository
    # The clock is a separate field so the repeat window is testable without time tricks.
    clock: Callable[[], float] = field(default=time.time)

    async def handle_message(
        self,
        api: ChatApi,
        *,
        chat_id: int,
        message_id: int,
        text: str | None,
        is_reply: bool = False,
        user_label: str = "unknown",
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
            # Without delete rights the bot is powerless, but silence is worse than speaking up.
            logger.error("failed to delete message %s in chat %s: %s", message_id, chat_id, exc)
            await self._notify_admins(
                api, f"Failed to delete message {message_id} in chat {chat_id}: {exc}"
            )
            return decision

        if not self.chat_settings.is_silent(chat_id):
            await api.send_message(chat_id, self.settings.on_delete_reply)

        report = (
            f"Deleted in chat {chat_id} from {user_label}: "
            f"{clip(text or '', REPORT_TEXT_BUDGET)}"
        )
        logger.info(report)
        # The button exists only if we know whom to ban: anonymous channel posts
        # have no author, and there is no one to ban. Administrators — the report's
        # recipients — are never offered the button: you can't ban your own.
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
            logger.warning("Could not notify administrators: %s", failure)

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
        """A kept message goes into the comparison base, and its copy to the administrators.

        We don't delete the repeat itself: a similarity threshold gives no
        guarantee, so silently erasing live ads is not allowed — the decision is
        left to the administrator.
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
