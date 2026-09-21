"""Модерация обычных сообщений."""

from __future__ import annotations

import logging
from functools import partial

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from bwbot.deps import Deps
from bwbot.handlers.extract import from_update
from bwbot.telegram_api import TelegramApi

logger = logging.getLogger(__name__)


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE, *, deps: Deps) -> None:
    incoming = from_update(update)
    if incoming is None:
        return

    decision = await deps.moderation.handle_message(
        TelegramApi(context.bot),
        chat_id=incoming.chat_id,
        message_id=incoming.message_id,
        text=incoming.text,
        is_reply=incoming.is_reply,
        user_label=incoming.user_label,
        user_id=incoming.user_id,
    )
    logger.info(
        "chat=%s msg=%s action=%s word=%s",
        incoming.chat_id,
        incoming.message_id,
        decision.action.value,
        decision.matched_word,
    )


def register(app: Application, deps: Deps) -> None:
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, partial(on_message, deps=deps)))
