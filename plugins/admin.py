from pyrogram import filters
from pyrogram.types import Message

from app.core.bot_client import bot
from app.core.tgcalls_client import call_py
from app.services.queue import get_queue, clear_queue, pop_current
from app.services.streamer import start_stream

@bot.on_message(filters.command("skip") & filters.group)
async def skip_command(_, message: Message):
    chat_id = message.chat.id
    queue = get_queue(chat_id)

    if not queue:
        return await message.reply_text("Queue is empty.")

    pop_current(chat_id)
    queue = get_queue(chat_id)

    if not queue:
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass
        return await message.reply_text("Skipped. Queue ended, left voice chat.")

    next_song = queue[0]
    await start_stream(chat_id, next_song["stream_url"])
    await message.reply_text(
        f"⏭ **Skipped**\n\nNow playing: **{next_song['title']}**"
    )

@bot.on_message(filters.command("stop") & filters.group)
async def stop_command(_, message: Message):
    chat_id = message.chat.id
    clear_queue(chat_id)
    try:
        await call_py.leave_call(chat_id)
    except Exception:
        pass
    await message.reply_text("⏹ Stopped streaming and cleared queue.")
