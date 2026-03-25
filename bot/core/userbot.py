from pyrogram import Client

from bot import config, logger


class Userbot(Client):
    def __init__(self):
        self.clients = []

        client_map = {
            "one": "STRING_SESSION",
            "two": "STRING_SESSION2",
            "three": "STRING_SESSION3",
        }

        for key, session_key in client_map.items():
            session_string = getattr(config, session_key)
            name = f"BikaUB{key[-1]}"

            setattr(
                self,
                key,
                Client(
                    name=name,
                    api_id=config.API_ID,
                    api_hash=config.API_HASH,
                    session_string=session_string,
                ),
            )

    async def boot_client(self, number: int, client: Client):
        clients = {
            1: self.one,
            2: self.two,
            3: self.three,
        }

        assistant = clients[number]
        await assistant.start()

        try:
            await assistant.send_message(config.LOGGER_ID, "Assistant Started")
        except Exception:
            raise SystemExit(
                f"Assistant {number} failed to send message in log group."
            )

        assistant.id = client.me.id
        assistant.name = client.me.first_name
        assistant.username = client.me.username
        assistant.mention = client.me.mention

        self.clients.append(assistant)

        try:
            await client.join_chat("Official_Bika")
        except Exception:
            pass

        logger.info(f"Assistant {number} started as @{assistant.username}")

    async def boot(self):
        if config.STRING_SESSION:
            await self.boot_client(1, self.one)
        if config.STRING_SESSION2:
            await self.boot_client(2, self.two)
        if config.STRING_SESSION3:
            await self.boot_client(3, self.three)

    async def exit(self):
        if config.STRING_SESSION:
            await self.one.stop()
        if config.STRING_SESSION2:
            await self.two.stop()
        if config.STRING_SESSION3:
            await self.three.stop()

        logger.info("Assistants stopped.")
