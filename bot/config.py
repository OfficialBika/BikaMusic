from os import getenv

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        # Telegram
        self.API_ID = int(getenv("API_ID", "0"))
        self.API_HASH = getenv("API_HASH")
        self.BOT_TOKEN = getenv("BOT_TOKEN")

        # Database
        self.MONGO_URL = getenv("MONGO_URL")

        # Main admins / logs
        self.OWNER_ID = int(getenv("OWNER_ID", "0"))
        self.LOGGER_ID = int(getenv("LOGGER_ID", "0"))

        # Limits
        self.DURATION_LIMIT = int(getenv("DURATION_LIMIT", "60")) * 60
        self.QUEUE_LIMIT = int(getenv("QUEUE_LIMIT", "20"))
        self.PLAYLIST_LIMIT = int(getenv("PLAYLIST_LIMIT", "20"))

        # Assistant sessions
        self.STRING_SESSION = getenv("SESSION")
        self.STRING_SESSION2 = getenv("SESSION2")
        self.STRING_SESSION3 = getenv("SESSION3")

        # Support links
        self.SUPPORT_CHAT = getenv(
            "SUPPORT_CHAT",
            "https://t.me/Myanmarbotcommunitychat",
        )
        self.SUPPORT_CHANNEL = getenv(
            "SUPPORT_CHANNEL",
            "https://t.me/MyanmarBotCommunity",
        )

        # Features
        self.AUTO_LEAVE = getenv("AUTO_LEAVE", "False").lower() == "true"
        self.AUTO_END = getenv("AUTO_END", "False").lower() == "true"
        self.THUMB_GEN = getenv("THUMB_GEN", "True").lower() == "true"
        self.VIDEO_PLAY = getenv("VIDEO_PLAY", "True").lower() == "true"

        # Language
        self.LANG_CODE = getenv("LANG_CODE", "en")

        # Cookies
        self.COOKIES_URL = [
            item
            for item in getenv("COOKIES_URL", "").split()
            if item and "batbin.me" in item
        ]

        # Images
        self.DEFAULT_THUMB = getenv(
            "DEFAULT_THUMB",
            "https://te.legra.ph/file/3e40a408286d4eda24191.jpg",
        )
        self.PING_IMG = getenv(
            "PING_IMG",
            "https://graph.org/file/f4d7fcd322e9b4ff71875-1bd81abda440766e3d.jpg",
        )
        self.START_IMG = getenv(
            "START_IMG",
            "https://graph.org/file/57c13c2b739bc2443c4f3-6a4fa57e870d529794.jpg",
        )
        self.HELP_IMG = getenv(
            "HELP_IMG",
            self.START_IMG,
        )

    def validate(self) -> None:
        required_keys = [
            "API_ID",
            "API_HASH",
            "BOT_TOKEN",
            "MONGO_URL",
            "LOGGER_ID",
            "OWNER_ID",
            "STRING_SESSION",
        ]

        missing_keys = [key for key in required_keys if not getattr(self, key)]
        if missing_keys:
            raise SystemExit(
                f"Missing required environment variables: {', '.join(missing_keys)}"
            )


config = Settings()
config.validate()
