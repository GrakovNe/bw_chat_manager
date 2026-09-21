"""Регистрация всех хендлеров."""

from __future__ import annotations

from telegram.ext import Application

from bwbot.deps import Deps
from bwbot.handlers import admin, messages, silent


def register_handlers(app: Application, deps: Deps) -> None:
    admin.register(app, deps)
    silent.register(app, deps)
    messages.register(app, deps)
