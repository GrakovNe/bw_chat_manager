"""The "Delete" button in a repeat report: removes the message left in the chat."""

from __future__ import annotations

from functools import partial

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from bwbot.callbacks import parse_delete_target
from bwbot.deps import Deps
from bwbot.handlers._callback import handle_button


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, *, deps: Deps) -> None:
    await handle_button(
        update,
        context,
        deps=deps,
        name="delete",
        parse=parse_delete_target,
        broken_reply=deps.settings.dup_broken_reply,
        action=deps.deletes.delete,
        note_template=deps.settings.dup_delete_done_note,
    )


def register(app: Application, deps: Deps) -> None:
    # The pattern is required: two callback handlers in one group; without a
    # filter both would fire on any button.
    app.add_handler(CallbackQueryHandler(partial(on_callback, deps=deps), pattern=r"^del:"))
