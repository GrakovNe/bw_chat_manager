"""Админ-команды: /start, /add, /delete_word, /list_words."""

from __future__ import annotations

import logging
from functools import partial

from telegram import Message, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from bwbot.deps import Deps
from bwbot.handlers.extract import IncomingMessage, from_update
from bwbot.services.admin import AdminResult
from bwbot.services.api import notify_all
from bwbot.telegram_api import TelegramApi
from bwbot.utils import normalize_word

logger = logging.getLogger(__name__)

START_TEXT = (
    "Привет! Я оставляю в чате только сообщения про дома и дворы BW.\n"
    "Админ-команды: /add, /delete_word, /list_words, /silent."
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, *, deps: Deps) -> None:
    del deps
    message = update.effective_message
    if message is not None:
        await message.reply_text(START_TEXT)


async def add_word(update: Update, context: ContextTypes.DEFAULT_TYPE, *, deps: Deps) -> None:
    authorized = await _require_admin(update, deps)
    if authorized is None:
        return
    message, incoming = authorized

    # «/add корпус 3» — это одно слово «корпус 3», а не две команды.
    argument = _argument(context)
    result = deps.word_admin.add_word(argument)
    await _reply_result(message, result)
    if result.ok:
        await _report_to_admins(
            context, deps, incoming, f"добавил(а) слово «{normalize_word(argument or '')}»"
        )


async def delete_word(update: Update, context: ContextTypes.DEFAULT_TYPE, *, deps: Deps) -> None:
    authorized = await _require_admin(update, deps)
    if authorized is None:
        return
    message, incoming = authorized

    # «/delete_word корпус 3» убирает ровно то же слово, что добавлял /add.
    argument = _argument(context)
    result = deps.word_admin.delete_word(argument)
    await _reply_result(message, result)
    if result.ok:
        await _report_to_admins(
            context, deps, incoming, f"удалил(а) слово «{normalize_word(argument or '')}»"
        )


async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE, *, deps: Deps) -> None:
    authorized = await _require_admin(update, deps)
    if authorized is None:
        return
    message, _ = authorized

    await _reply_result(message, deps.word_admin.list_words())


async def _require_admin(update: Update, deps: Deps) -> tuple[Message, IncomingMessage] | None:
    """Сообщение и данные автора, если автор — администратор бота. Иначе отвечает «нельзя»."""
    message = update.effective_message
    if message is None:
        return None
    incoming = from_update(update)
    if not deps.settings.is_admin(incoming.user_id if incoming else None):
        await message.reply_text(deps.settings.not_admin_reply)
        return None
    return message, incoming


def _argument(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    return " ".join(context.args) if context.args else None


async def _reply_result(message: Message, result: AdminResult) -> None:
    await message.reply_text(result.message)
    for chunk in result.extra_chunks:
        await message.reply_text(chunk)


async def _report_to_admins(
    context: ContextTypes.DEFAULT_TYPE, deps: Deps, incoming: IncomingMessage, action: str
) -> None:
    text = f"{incoming.user_label} {action} в чате {incoming.chat_id}."
    recipients = [admin_id for admin_id in deps.settings.admin_ids if admin_id != incoming.user_id]
    failures = await notify_all(TelegramApi(context.bot), recipients, text)
    for failure in failures:
        logger.warning("Не удалось уведомить администраторов: %s", failure)


def register(app: Application, deps: Deps) -> None:
    app.add_handler(CommandHandler("start", partial(start, deps=deps)))
    app.add_handler(CommandHandler("add", partial(add_word, deps=deps)))
    app.add_handler(CommandHandler("delete_word", partial(delete_word, deps=deps)))
    app.add_handler(CommandHandler("list_words", partial(list_words, deps=deps)))
