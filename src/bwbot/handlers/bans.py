"""Кнопка BAN в отчёте об удалении: выкидывает автора из того же чата."""

from __future__ import annotations

import logging
from functools import partial
from typing import Any

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from bwbot.callbacks import parse_ban_target
from bwbot.deps import Deps
from bwbot.telegram_api import TelegramApi
from bwbot.utils import append_note

logger = logging.getLogger(__name__)

BAN_DONE_NOTE = "⛔ Забанен администратором {by}"


def _user_label(user: Any) -> str:
    if user is None:
        return "неизвестный"
    return user.username or user.full_name or "аноним"


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, *, deps: Deps) -> None:
    query = update.callback_query
    if query is None:
        return

    api = TelegramApi(context.bot)
    by = _user_label(query.from_user)
    target = parse_ban_target(query.data)

    if target is None:
        await api.answer_callback(query.id, deps.settings.ban_broken_reply)
        return

    presser_id = query.from_user.id if query.from_user else None
    if not deps.settings.is_admin(presser_id):
        logger.warning("ban denied: chat=%s user=%s by=%s", target.chat_id, target.user_id, by)
        await api.answer_callback(query.id, deps.settings.not_admin_reply)
        return

    result = await deps.bans.ban(api, target, by=by)
    await api.answer_callback(query.id, result.message)
    if not result.ok:
        # Кнопку оставляем: ошибку прав можно починить и нажать снова.
        return

    await _mark_report_banned(api, query, by)


async def _mark_report_banned(api: TelegramApi, query: Any, by: str) -> None:
    """Снимает кнопку и дописывает итог, чтобы не жали по одному отчёту дважды."""
    message = query.message
    text = getattr(message, "text", None)
    if message is None or not text:
        return

    try:
        await api.edit_message_text(
            message.chat_id,
            message.message_id,
            append_note(text, BAN_DONE_NOTE.format(by=by)),
        )
    except TelegramError:
        logger.warning("Не удалось обновить отчёт об удалении", exc_info=True)


def register(app: Application, deps: Deps) -> None:
    app.add_handler(CallbackQueryHandler(partial(on_callback, deps=deps)))
