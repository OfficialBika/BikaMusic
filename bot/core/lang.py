import json
from functools import wraps
from pathlib import Path

from pyrogram import errors

from bot import db, logger

lang_codes = {
    "ar": "العربية",
    "en": "English",
    "ja": "日本語",
    "my": "မြန်မာဘာသာ",
    "zh": "中文",
}


class Language:
    def __init__(self):
        self.lang_codes = lang_codes
        self.lang_dir = Path("bot/locales")
        self.languages = self.load_files()

    def load_files(self):
        languages = {}
        lang_files = {file.stem: file for file in self.lang_dir.glob("*.json")}

        for lang_code, lang_file in lang_files.items():
            if lang_code not in self.lang_codes:
                continue

            with open(lang_file, "r", encoding="utf-8") as file:
                languages[lang_code] = json.load(file)

        logger.info(f"Loaded languages: {', '.join(languages.keys())}")
        return languages

    async def get_lang(self, chat_id: int) -> dict:
        lang_code = await db.get_lang(chat_id)
        return self.languages[lang_code]

    def get_languages(self) -> dict:
        files = {f.stem for f in self.lang_dir.glob("*.json")}
        return {
            code: self.lang_codes[code]
            for code in sorted(files)
            if code in self.lang_codes
        }

    def language(self):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                fallen = next(
                    (
                        arg
                        for arg in args
                        if hasattr(arg, "chat") or hasattr(arg, "message")
                    ),
                    None,
                )

                if not fallen or not fallen.from_user:
                    return

                if hasattr(fallen, "chat"):
                    chat = fallen.chat
                elif hasattr(fallen, "message"):
                    chat = fallen.message.chat
                else:
                    chat = None

                if not chat:
                    return

                if chat.id in db.blacklist_cache:
                    logger.info(f"Chat {chat.id} is blacklisted, leaving...")
                    return await chat.leave()

                lang_code = await db.get_lang(chat.id)
                lang_dict = self.languages[lang_code]

                setattr(fallen, "lang", lang_dict)

                try:
                    return await func(*args, **kwargs)
                except (
                    errors.ChannelPrivate,
                    errors.MessageIdInvalid,
                    errors.MessageNotModified,
                ):
                    return
                except (
                    errors.Forbidden,
                    errors.exceptions.Forbidden,
                    errors.ChatWriteForbidden,
                    errors.exceptions.ChatWriteForbidden,
                ):
                    return

            return wrapper

        return decorator
