"""ChatApi implementation over telegram.Bot."""

from __future__ import annotations

from collections.abc import Sequence

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.error import TelegramError

from bwbot.services.api import ApiError, Button


def _markup(buttons: Sequence[Button]) -> InlineKeyboardMarkup | None:
    """One button per row: exactly one ban button lives under a report."""
    if not buttons:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=data)] for label, data in buttons]
    )


# Reports contain the offender's text: someone else's link must not blow up
# into an image in the chat or in the administrators' private messages.
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
        """Bans and kicks from the chat. A Telegram refusal becomes an ApiError with the reason."""
        try:
            await self.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        except TelegramError as exc:
            raise ApiError(str(exc)) from exc
