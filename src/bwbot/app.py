"""Сборка Telegram Application из настроек и зависимостей."""

from __future__ import annotations

import logging

from telegram.ext import Application, ContextTypes

from bwbot.config import Settings
from bwbot.deps import Deps
from bwbot.handlers import register_handlers

logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Необработанная ошибка в хендлере", exc_info=context.error)


def build_application(settings: Settings, deps: Deps | None = None) -> Application:
    resolved = deps if deps is not None else Deps.build(settings)
    app = Application.builder().token(settings.token).build()
    register_handlers(app, resolved)
    app.add_error_handler(on_error)
    return app
