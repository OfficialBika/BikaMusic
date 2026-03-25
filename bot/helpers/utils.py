
import re

from pyrogram import enums, types

from bot import app


class Utilities:
    def __init__(self):
        pass

    def format_eta(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}:{seconds % 60:02d} min"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            return f"{hours}:{minutes:02d}:{secs:02d} h"

    def format_size(self, bytes: int) -> str:
        if bytes >= 1024**3:
            return f"{bytes / 1024**3:.2f} GB"
        elif bytes >= 1024**2:
            return f"{bytes / 1024**2:.2f} MB"
        else:
            return f"{bytes / 1024:.2f} KB"

    def to_seconds(self, time: str) -> int:
        parts = [int(part) for part in time.strip().split(":")]
        return sum(value * 60**i for i, value in enumerate(reversed(parts)))

    def get_url(self, message: types.Message) -> str | None:
        url = None
        messages = [message]

        if message.reply_to_message:
            messages.append(message.reply_to_message)

        for msg in messages:
            entities = msg.entities or msg.caption_entities or []

            for entity in entities:
                if entity.type == enums.MessageEntityType.TEXT_LINK:
                    url = entity.url
                    break
                elif entity.type == enums.MessageEntityType.URL:
                    text = msg.text or msg.caption
                    if not text:
                        continue
                    url = text[entity.offset : entity.offset + entity.length]
                    break

        if url:
            return url.split("&si")[0].split("?si")[0]
        return None

    async def extract_user(self, message: types.Message) -> types.User | None:
        if message.reply_to_message:
            return message.reply_to_message.from_user

        if message.entities:
            for entity in message.entities:
                if entity.type == enums.MessageEntityType.TEXT_MENTION:
                    return entity.user

        if message.text:
            try:
                if mention := re.search(r"@(\w{5,32})", message.text):
                    return await app.get_users(mention.group(0))
                if user_id := re.search(r"\b\d{6,15}\b", message.text):
                    return await app.get_users(int(user_id.group(0)))
            except Exception:
                pass

        return None

    async def play_log(
        self,
        message: types.Message,
        link: str,
        title: str,
        duration: str,
    ) -> None:
        if message.chat.id == app.logger:
            return

        text = message.lang["play_log"].format(
            app.name,
            message.chat.id,
            message.chat.title,
            message.from_user.id,
            message.from_user.mention,
            link,
            title,
            duration,
        )
        await app.send_message(chat_id=app.logger, text=text)

    async def send_log(self, message: types.Message, chat: bool = False) -> None:
        if chat:
            user = message.from_user
            return await app.send_message(
                chat_id=app.logger,
                text=message.lang["log_chat"].format(
                    message.chat.id,
                    message.chat.title,
                    user.id if user else 0,
                    user.mention if user else "Anonymous",
                ),
            )

        await app.send_message(
            chat_id=app.logger,
            text=message.lang["log_user"].format(
                message.from_user.id,
                f"@{message.from_user.username}",
                message.from_user.mention,
            ),
      )
