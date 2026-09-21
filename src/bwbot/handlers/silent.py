"""/silent on|off — отключает ответы бота об удалении в конкретном чате."""

from __future__ import annotations

import logging
from functools import partial

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bwbot.deps import Deps
from bwbot.handlers.extract import from_update

logger = logging.getLogger(__name__)

ON = "on"
OFF = "off"


async def silent(update: Update, context: ContextTypes.DEFAULT_TYPE, *, deps: Deps) -> None:
    message = update.effective_message
    incoming = from_update(update)
    if message is None or incoming is None:
        return

    argument = context.args[0].lower() if context.args else ""
    if argument not in (ON, OFF):
        await message.reply_text(deps.settings.silent_usage_reply)
        return

    enabled = argument == ON
    deps.chat_settings.set_silent(incoming.chat_id, enabled)
    logger.info("chat=%s silent=%s by=%s", incoming.chat_id, enabled, incoming.user_label)
    await message.reply_text(
        deps.settings.silent_on_reply if enabled else deps.settings.silent_off_reply
    )


def register(app: Application, deps: Deps) -> None:
    app.add_handler(CommandHandler("silent", partial(silent, deps=deps)))
