"""Общий каркас ответа на нажатие кнопки под отчётом.

Бан и удаление различаются только тем, что делают: разбор цели, текст про
битую кнопку, само действие и пометка об итоге. Проверка прав, ответ нажателю
и обновление отчёта — одна и та же последовательность, живёт здесь.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bwbot.deps import Deps
from bwbot.handlers.extract import user_label
from bwbot.services.api import ChatApi
from bwbot.services.result import ActionResult
from bwbot.telegram_api import TelegramApi
from bwbot.utils import append_note

logger = logging.getLogger(__name__)

# Разбор callback_data: строка -> цель нажатия или None, если кнопка не понята.
Parse = Callable[[str | None], Any]
# Действие администратора: (api, target, *, by) -> исход.
Action = Callable[..., Awaitable[ActionResult]]


async def handle_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    deps: Deps,
    name: str,
    parse: Parse,
    broken_reply: str,
    action: Action,
    note_template: str,
) -> None:
    query = update.callback_query
    if query is None:
        return

    api = TelegramApi(context.bot)
    by = user_label(query.from_user)
    target = parse(query.data)
    if target is None:
        await api.answer_callback(query.id, broken_reply)
        return

    presser_id = query.from_user.id if query.from_user else None
    if not deps.settings.is_admin(presser_id):
        logger.warning("%s denied: target=%s presser=%s", name, target, presser_id)
        await api.answer_callback(query.id, deps.settings.not_admin_reply)
        return

    result = await action(api, target, by=by)
    await api.answer_callback(query.id, result.message)
    if not result.ok:
        # Кнопку оставляем: причину отказа можно устранить и нажать снова.
        return

    await _mark_report(api, query, note_template.format(by=by), name)


async def _mark_report(api: ChatApi, query: Any, note: str, name: str) -> None:
    """Снимает кнопку и дописывает итог, чтобы по одному отчёту жали один раз."""
    message = query.message
    text = getattr(message, "text", None)
    if message is None or not text:
        return

    try:
        await api.edit_message_text(
            message.chat_id,
            message.message_id,
            append_note(text, note),
        )
    except TelegramError:
        logger.warning("Не удалось обновить отчёт (%s)", name, exc_info=True)
