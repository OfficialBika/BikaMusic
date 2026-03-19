import asyncio
from app.core.bot_client import bot
from app.core.userbot_client import assistant
from app.core.tgcalls_client import call_py

async def main():
    await assistant.start()
    print("Assistant started")

    await bot.start()
    print("Bot started")

    await call_py.start()
    print("PyTgCalls started")

    print("BIKA Music Bot is running...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
