"""Deleting a message via the button in a repeat report."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from bwbot.callbacks import DeleteTarget
from bwbot.config import Settings
from bwbot.services.api import ApiError, ChatApi
from bwbot.services.result import ActionResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeleteService:
    settings: Settings

    async def delete(self, api: ChatApi, target: DeleteTarget, *, by: str) -> ActionResult:
        try:
            await api.delete_message(target.chat_id, target.message_id)
        except ApiError as exc:
            # Most often the message was already deleted manually or is too old.
            logger.warning(
                "delete failed: chat=%s message=%s by=%s reason=%s",
                target.chat_id,
                target.message_id,
                by,
                exc,
            )
            return ActionResult(ok=False, message=f"{self.settings.dup_delete_failed_reply} {exc}")

        logger.info(
            "repeat deleted: chat=%s message=%s by=%s", target.chat_id, target.message_id, by
        )
        return ActionResult(ok=True, message=self.settings.dup_deleted_reply)
