
import asyncio
import importlib
import signal
from contextlib import suppress

from bot import anon, app, config, db, logger, stop, thumb, userbot, yt
from bot.plugins import all_modules


async def idle() -> None:
    loop = asyncio.get_running_loop()
    waiter = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, waiter.set)

    await waiter.wait()


async def main() -> None:
    await db.connect()
    await app.boot()
    await userbot.boot()
    await anon.boot()
    await thumb.start()

    for module in all_modules:
        importlib.import_module(f"bot.plugins.{module}")
    logger.info(f"Loaded {len(all_modules)} modules.")

    if config.COOKIES_URL:
        await yt.save_cookies(config.COOKIES_URL)

    sudo_users = await db.get_sudoers()
    app.sudoers.update(sudo_users)
    app.bl_users.update(await db.get_blacklisted())
    logger.info(f"Loaded {len(app.sudoers)} sudo users.")

    await idle()
    await stop()


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        pass
