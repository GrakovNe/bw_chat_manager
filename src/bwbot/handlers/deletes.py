"""Кнопка «Удалить» в отчёте о повторе: убирает сообщение, оставшееся в чате."""

from __future__ import annotations

import logging
from functools import partial
from typing import Any

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from bwbot.callbacks import parse_delete_target
from bwbot.deps import Deps
from bwbot.handlers.extract import user_label
from bwbot.telegram_api import TelegramApi
from bwbot.utils import append_note

logger = logging.getLogger(__name__)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, *, deps: Deps) -> None:
    query = update.callback_query
    if query is None:
        return

    api = TelegramApi(context.bot)
    by = user_label(query.from_user)
    target = parse_delete_target(query.data)

    if target is None:
        await api.answer_callback(query.id, deps.settings.dup_broken_reply)
        return

    presser_id = query.from_user.id if query.from_user else None
    if not deps.settings.is_admin(presser_id):
        logger.warning(
            "delete denied: chat=%s message=%s by=%s", target.chat_id, target.message_id, by
        )
        await api.answer_callback(query.id, deps.settings.not_admin_reply)
        return

    result = await deps.deletes.delete(api, target, by=by)
    await api.answer_callback(query.id, result.message)
    if not result.ok:
        # Кнопку оставляем: возможно, удаление не прошло по временной причине.
        return

    await _mark_report_deleted(api, query, by, deps.settings.dup_delete_done_note)


async def _mark_report_deleted(api: TelegramApi, query: Any, by: str, note_template: str) -> None:
    """Снимает кнопку и дописывает итог: удалять одно сообщение дважды незачем."""
    message = query.message
    text = getattr(message, "text", None)
    if message is None or not text:
        return

    try:
        await api.edit_message_text(
            message.chat_id,
            message.message_id,
            append_note(text, note_template.format(by=by)),
        )
    except TelegramError:
        logger.warning("Не удалось обновить отчёт о повторе", exc_info=True)


def register(app: Application, deps: Deps) -> None:
    # Pattern обязателен: в одной группе два callback-хендлера, без фильтра они
    # оба отрабатывали бы на любой кнопке.
    app.add_handler(CallbackQueryHandler(partial(on_callback, deps=deps), pattern=r"^del:"))
