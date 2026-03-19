from pyrogram import filters
from pyrogram.types import Message
from app.core.bot_client import bot
from app.services.queue import get_queue

@bot.on_message(filters.command("queue") & filters.group)
async def queue_command(_, message: Message):
    chat_id = message.chat.id
    queue = get_queue(chat_id)

    if not queue:
        return await message.reply_text("Queue is empty.")

    text = "**Current Queue:**\n\n"
    for i, item in enumerate(queue, start=1):
        text += f"{i}. {item['title']}\n"

    await message.reply_text(text)
