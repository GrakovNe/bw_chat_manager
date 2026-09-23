"""Кнопка BAN в отчёте об удалении: выкидывает автора из того же чата."""

from __future__ import annotations

from functools import partial

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from bwbot.callbacks import parse_ban_target
from bwbot.deps import Deps
from bwbot.handlers._callback import handle_button

BAN_DONE_NOTE = "⛔ Забанен администратором {by}"


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, *, deps: Deps) -> None:
    await handle_button(
        update,
        context,
        deps=deps,
        name="ban",
        parse=parse_ban_target,
        broken_reply=deps.settings.ban_broken_reply,
        action=deps.bans.ban,
        note_template=BAN_DONE_NOTE,
    )


def register(app: Application, deps: Deps) -> None:
    # Pattern обязателен: в одной группе два callback-хендлера, без фильтра они
    # оба отрабатывали бы на любой кнопке.
    app.add_handler(CallbackQueryHandler(partial(on_callback, deps=deps), pattern=r"^ban:"))
