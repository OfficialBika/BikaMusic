
from pyrogram import Client, enums, filters, types

from bot import config, logger


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="BikaMusic",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            parse_mode=enums.ParseMode.HTML,
            max_concurrent_transmissions=7,
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )

        self.owner = config.OWNER_ID
        self.logger = config.LOGGER_ID
        self.bl_users = filters.user()
        self.sudoers = filters.user(self.owner)

    async def boot(self):
        await super().start()

        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        self.mention = self.me.mention

        try:
            await self.send_message(self.logger, "Bot Started")
            get = await self.get_chat_member(self.logger, self.id)
        except Exception as ex:
            raise SystemExit(
                f"Bot has failed to access the log group: {self.logger}\nReason: {ex}"
            )

        if get.status not in (
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
        ):
            raise SystemExit("Please promote the bot as an admin in logger group.")

        logger.info(f"Bot started as @{self.username}")

    async def exit(self):
        await super().stop()
        logger.info("Bot stopped.")
