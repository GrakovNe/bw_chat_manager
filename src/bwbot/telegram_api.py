"""Реализация ChatApi поверх telegram.Bot."""

from __future__ import annotations

from collections.abc import Sequence

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.error import TelegramError

from bwbot.services.api import ApiError, Button


def _markup(buttons: Sequence[Button]) -> InlineKeyboardMarkup | None:
    """Одна кнопка в ряд: под отчётом живёт ровно одна кнопка бана."""
    if not buttons:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data)] for label, data in buttons]
    )


# Отчёты содержат текст нарушителя: чужая ссылка не должна разрастаться
# картинкой ни в чате, ни в личных сообщениях администраторам.
_NO_PREVIEW = LinkPreviewOptions(is_disabled=True)


class TelegramApi:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        try:
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
        except TelegramError as exc:
            raise ApiError(str(exc)) from exc

    async def send_message(self, chat_id: int, text: str, buttons: Sequence[Button] = ()) -> None:
        await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=_markup(buttons),
            link_preview_options=_NO_PREVIEW,
        )

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        buttons: Sequence[Button] = (),
    ) -> None:
        await self.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=_markup(buttons),
        )

    async def answer_callback(self, callback_id: str, text: str) -> None:
        await self.bot.answer_callback_query(callback_query_id=callback_id, text=text)

    async def ban_chat_member(self, chat_id: int, user_id: int) -> None:
        """Банит и выкидывает из чата. Отказ Telegram превращаем в ApiError с причиной."""
        try:
            await self.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        except TelegramError as exc:
            raise ApiError(str(exc)) from exc
