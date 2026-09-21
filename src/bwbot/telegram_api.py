"""Реализация ChatApi поверх telegram.Bot."""

from __future__ import annotations

from dataclasses import dataclass

from telegram import Bot


@dataclass
class TelegramApi:
    bot: Bot

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        await self.bot.delete_message(chat_id=chat_id, message_id=message_id)

    async def send_message(self, chat_id: int, text: str) -> None:
        await self.bot.send_message(chat_id=chat_id, text=text)
