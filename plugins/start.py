from pyrogram import filters
from pyrogram.types import Message
from app.core.bot_client import bot
from config import BOT_NAME

@bot.on_message(filters.command("start"))
async def start_command(_, message: Message):
    text = (
        f"**{BOT_NAME}**\n\n"
        "Hello! I am a Telegram Voice Chat Music Bot.\n\n"
        "Commands:\n"
        "/start - Start the bot\n"
        "/help - Show help\n"
        "/play <song name> - Play music\n"
        "/queue - Show queue\n"
        "/skip - Skip current song\n"
        "/stop - Stop streaming"
    )
    await message.reply_text(text)

@bot.on_message(filters.command("help"))
async def help_command(_, message: Message):
    text = (
        "**Help Menu**\n\n"
        "/play <name> - Search and play song\n"
        "/queue - Show current queue\n"
        "/skip - Skip current playing song\n"
        "/stop - Stop player and clear queue"
    )
    await message.reply_text(text)
