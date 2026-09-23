"""Registration of all handlers."""

from __future__ import annotations

from telegram.ext import Application

from bwbot.deps import Deps
from bwbot.handlers import admin, bans, deletes, messages, silent


def register_handlers(app: Application, deps: Deps) -> None:
    admin.register(app, deps)
    silent.register(app, deps)
    messages.register(app, deps)
    bans.register(app, deps)
    deletes.register(app, deps)
