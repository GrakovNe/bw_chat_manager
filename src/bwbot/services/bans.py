"""Banning an offender: we kick them out of the chat where they wrote."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from bwbot.callbacks import BanTarget
from bwbot.config import Settings
from bwbot.services.api import ApiError, ChatApi
from bwbot.services.result import ActionResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BanService:
    settings: Settings

    async def ban(self, api: ChatApi, target: BanTarget, *, by: str) -> ActionResult:
        if self.settings.is_admin(target.user_id):
            logger.warning("ban refused for admin: chat=%s user=%s", target.chat_id, target.user_id)
            return ActionResult(ok=False, message=self.settings.ban_admin_reply)

        try:
            await api.ban_chat_member(target.chat_id, target.user_id)
        except ApiError as exc:
            logger.warning(
                "ban failed: chat=%s user=%s by=%s reason=%s",
                target.chat_id,
                target.user_id,
                by,
                exc,
            )
            return ActionResult(ok=False, message=f"{self.settings.ban_failed_reply} {exc}")

        logger.info("ban chat=%s user=%s by=%s", target.chat_id, target.user_id, by)
        return ActionResult(ok=True, message=self.settings.ban_done_reply)
