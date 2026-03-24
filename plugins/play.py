from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import UserAlreadyParticipant

from app.core.bot_client import bot
from app.core.userbot_client import assistant
from app.services.youtube import search_youtube
from app.services.streamer import start_stream
from app.services.queue import add_to_queue, get_queue, clear_queue, pop_current

@bot.on_message(filters.command("play") & filters.group)
async def play_command(_, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /play song name")

    query = " ".join(message.command[1:])
    chat_id = message.chat.id

    msg = await message.reply_text("Searching...")

    try:
        try:
            await assistant.join_chat(message.chat.username or chat_id)
        except UserAlreadyParticipant:
            pass
        except Exception:
            pass

        result = await search_youtube(query)

        item = {
            "title": result["title"],
            "stream_url": result["url"],
            "link": result["webpage_url"],
            "requested_by": message.from_user.mention if message.from_user else "Unknown",
        }

        queue_length = add_to_queue(chat_id, item)

        if queue_length == 1:
            await start_stream(chat_id, item["stream_url"])
            await msg.edit_text(
                f"▶️ **Started Streaming**\n\n"
                f"**Title:** {item['title']}\n"
                f"**Requested by:** {item['requested_by']}\n"
                f"**Link:** {item['link']}"
            )
        else:
            await msg.edit_text(
                f"➕ **Added to Queue**\n\n"
                f"**Title:** {item['title']}\n"
                f"**Position:** {queue_length}\n"
                f"**Requested by:** {item['requested_by']}"
            )
    except Exception as e:
        await msg.edit_text(f"Error:\n`{e}`")
