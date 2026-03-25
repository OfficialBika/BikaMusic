
from random import randint
from time import time

from pymongo import AsyncMongoClient

from bot import config, logger, userbot


class MongoDB:
    def __init__(self):
        self.mongo = AsyncMongoClient(
            config.MONGO_URL,
            serverSelectionTimeoutMS=12500,
        )
        self.db = self.mongo.BikaMusic

        self.admins_cache = {}
        self.call_cache = {}
        self.admin_play_cache = []
        self.blacklist_cache = []
        self.cmd_delete_cache = []
        self.loop_cache = {}
        self.notify_cache = []

        self.cache = self.db.cache
        self.logger_state = False

        self.assistant_cache = {}
        self.assistantdb = self.db.assistant

        self.auth_cache = {}
        self.authdb = self.db.auth

        self.chat_cache = []
        self.chatsdb = self.db.chats

        self.lang_cache = {}
        self.langdb = self.db.lang

        self.user_cache = []
        self.usersdb = self.db.users

    async def connect(self) -> None:
        try:
            started_at = time()
            await self.mongo.admin.command("ping")
            logger.info(
                f"Database connection successful. ({time() - started_at:.2f}s)"
            )
            await self.load_cache()
        except Exception as exc:
            raise SystemExit(
                f"Database connection failed: {type(exc).__name__}"
            ) from exc

    async def close(self) -> None:
        await self.mongo.close()
        logger.info("Database connection closed.")

    # CALL CACHE
    async def get_call(self, chat_id: int) -> bool:
        return chat_id in self.call_cache

    async def add_call(self, chat_id: int) -> None:
        self.call_cache[chat_id] = 1

    async def remove_call(self, chat_id: int) -> None:
        self.call_cache.pop(chat_id, None)

    async def playing(self, chat_id: int, paused: bool = None) -> bool | None:
        if paused is not None:
            self.call_cache[chat_id] = int(not paused)
        return bool(self.call_cache.get(chat_id, 0))

    async def get_admins(self, chat_id: int, reload: bool = False) -> list[int]:
        from bot.helpers._admins import reload_admins

        if chat_id not in self.admins_cache or reload:
            self.admins_cache[chat_id] = await reload_admins(chat_id)
        return self.admins_cache[chat_id]

    async def get_loop(self, chat_id: int) -> int:
        return self.loop_cache.get(chat_id, 0)

    async def set_loop(self, chat_id: int, count: int) -> None:
        self.loop_cache[chat_id] = count

    # AUTH METHODS
    async def _get_auth(self, chat_id: int) -> set[int]:
        if chat_id not in self.auth_cache:
            doc = await self.authdb.find_one({"_id": chat_id}) or {}
            self.auth_cache[chat_id] = set(doc.get("user_ids", []))
        return self.auth_cache[chat_id]

    async def is_auth(self, chat_id: int, user_id: int) -> bool:
        return user_id in await self._get_auth(chat_id)

    async def add_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id not in users:
            users.add(user_id)
            await self.authdb.update_one(
                {"_id": chat_id},
                {"$addToSet": {"user_ids": user_id}},
                upsert=True,
            )

    async def rm_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id in users:
            users.discard(user_id)
            await self.authdb.update_one(
                {"_id": chat_id},
                {"$pull": {"user_ids": user_id}},
            )

    # ASSISTANT METHODS
    async def set_assistant(self, chat_id: int) -> int:
        number = randint(1, len(userbot.clients))
        await self.assistantdb.update_one(
            {"_id": chat_id},
            {"$set": {"num": number}},
            upsert=True,
        )
        self.assistant_cache[chat_id] = number
        return number

    async def get_assistant(self, chat_id: int):
        from bot import anon

        if chat_id not in self.assistant_cache:
            doc = await self.assistantdb.find_one({"_id": chat_id})
            number = doc["num"] if doc else await self.set_assistant(chat_id)
            self.assistant_cache[chat_id] = number

        return anon.clients[self.assistant_cache[chat_id] - 1]

    async def get_client(self, chat_id: int):
        if chat_id not in self.assistant_cache:
            await self.get_assistant(chat_id)

        return {
            1: userbot.one,
            2: userbot.two,
            3: userbot.three,
        }.get(self.assistant_cache[chat_id])

    # BLACKLIST METHODS
    async def add_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            self.blacklist_cache.append(chat_id)
            return await self.cache.update_one(
                {"_id": "bl_chats"},
                {"$addToSet": {"chat_ids": chat_id}},
                upsert=True,
            )

        await self.cache.update_one(
            {"_id": "bl_users"},
            {"$addToSet": {"user_ids": chat_id}},
            upsert=True,
        )

    async def del_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            if chat_id in self.blacklist_cache:
                self.blacklist_cache.remove(chat_id)
            return await self.cache.update_one(
                {"_id": "bl_chats"},
                {"$pull": {"chat_ids": chat_id}},
            )

        await self.cache.update_one(
            {"_id": "bl_users"},
            {"$pull": {"user_ids": chat_id}},
        )

    async def get_blacklisted(self, chat: bool = False) -> list[int]:
        if chat:
            if not self.blacklist_cache:
                doc = await self.cache.find_one({"_id": "bl_chats"})
                self.blacklist_cache.extend(doc.get("chat_ids", []) if doc else [])
            return self.blacklist_cache

        doc = await self.cache.find_one({"_id": "bl_users"})
        return doc.get("user_ids", []) if doc else []

    # CHAT METHODS
    async def is_chat(self, chat_id: int) -> bool:
        return chat_id in self.chat_cache

    async def add_chat(self, chat_id: int) -> None:
        if not await self.is_chat(chat_id):
            self.chat_cache.append(chat_id)
            await self.chatsdb.insert_one({"_id": chat_id})

    async def rm_chat(self, chat_id: int) -> None:
        if await self.is_chat(chat_id):
            self.chat_cache.remove(chat_id)
            await self.chatsdb.delete_one({"_id": chat_id})

    async def get_chats(self) -> list:
        if not self.chat_cache:
            self.chat_cache.extend(
                [chat["_id"] async for chat in self.chatsdb.find()]
            )
        return self.chat_cache

    # COMMAND DELETE
    async def get_cmd_delete(self, chat_id: int) -> bool:
        if chat_id not in self.cmd_delete_cache:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("cmd_delete"):
                self.cmd_delete_cache.append(chat_id)
        return chat_id in self.cmd_delete_cache

    async def set_cmd_delete(self, chat_id: int, delete: bool = False) -> None:
        if delete:
            if chat_id not in self.cmd_delete_cache:
                self.cmd_delete_cache.append(chat_id)
        else:
            if chat_id in self.cmd_delete_cache:
                self.cmd_delete_cache.remove(chat_id)

        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"cmd_delete": delete}},
            upsert=True,
        )

    # LANGUAGE METHODS
    async def set_lang(self, chat_id: int, lang_code: str):
        await self.langdb.update_one(
            {"_id": chat_id},
            {"$set": {"lang": lang_code}},
            upsert=True,
        )
        self.lang_cache[chat_id] = lang_code

    async def get_lang(self, chat_id: int) -> str:
        if chat_id not in self.lang_cache:
            doc = await self.langdb.find_one({"_id": chat_id})
            self.lang_cache[chat_id] = doc["lang"] if doc else config.LANG_CODE
        return self.lang_cache[chat_id]

    # LOGGER METHODS
    async def is_logger(self) -> bool:
        return self.logger_state

    async def get_logger(self) -> bool:
        doc = await self.cache.find_one({"_id": "logger"})
        if doc:
            self.logger_state = doc["status"]
        return self.logger_state

    async def set_logger(self, status: bool) -> None:
        self.logger_state = status
        await self.cache.update_one(
            {"_id": "logger"},
            {"$set": {"status": status}},
            upsert=True,
        )

    # PLAY MODE METHODS
    async def get_play_mode(self, chat_id: int) -> bool:
        if chat_id not in self.admin_play_cache:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("admin_play"):
                self.admin_play_cache.append(chat_id)
        return chat_id in self.admin_play_cache

    async def set_play_mode(self, chat_id: int, remove: bool = False) -> None:
        if remove:
            if chat_id in self.admin_play_cache:
                self.admin_play_cache.remove(chat_id)
        else:
            if chat_id not in self.admin_play_cache:
                self.admin_play_cache.append(chat_id)

        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"admin_play": not remove}},
            upsert=True,
        )

    # SUDO METHODS
    async def add_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"},
            {"$addToSet": {"user_ids": user_id}},
            upsert=True,
        )

    async def del_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"},
            {"$pull": {"user_ids": user_id}},
        )

    async def get_sudoers(self) -> list[int]:
        doc = await self.cache.find_one({"_id": "sudoers"})
        return doc.get("user_ids", []) if doc else []

    # USER METHODS
    async def is_user(self, user_id: int) -> bool:
        return user_id in self.user_cache

    async def add_user(self, user_id: int) -> None:
        if not await self.is_user(user_id):
            self.user_cache.append(user_id)
            await self.usersdb.insert_one({"_id": user_id})

    async def rm_user(self, user_id: int) -> None:
        if await self.is_user(user_id):
            self.user_cache.remove(user_id)
            await self.usersdb.delete_one({"_id": user_id})

    async def get_users(self) -> list:
        if not self.user_cache:
            self.user_cache.extend(
                [user["_id"] async for user in self.usersdb.find()]
            )
        return self.user_cache

    async def migrate_coll(self) -> None:
        logger.info("Migrating users and chats from old collections...")

        all_users, migrated_users, migrated_chats = [], [], []
        seen_user_ids, seen_chat_ids = set(), set()

        all_users.extend([user async for user in self.usersdb.find()])
        all_users.extend([user async for user in self.db.tgusersdb.find()])

        for user in all_users:
            _id = user.get("_id")
            user_id = _id if isinstance(_id, int) else int(user.get("user_id"))

            if user_id in seen_user_ids:
                continue

            seen_user_ids.add(user_id)
            migrated_users.append({"_id": user_id})

        await self.usersdb.drop()
        await self.db.tgusersdb.drop()

        if migrated_users:
            await self.usersdb.insert_many(migrated_users)

        async for chat in self.chatsdb.find():
            _id = chat.get("_id")
            chat_id = _id if isinstance(_id, int) else int(chat.get("chat_id"))

            if chat_id in seen_chat_ids:
                continue

            seen_chat_ids.add(chat_id)
            migrated_chats.append({"_id": chat_id})

        await self.chatsdb.drop()

        if migrated_chats:
            await self.chatsdb.insert_many(migrated_chats)

        await self.cache.insert_one({"_id": "migrated"})
        logger.info("Migration completed successfully.")

    async def load_cache(self) -> None:
        doc = await self.cache.find_one({"_id": "migrated"})
        if not doc:
            await self.migrate_coll()

        await self.get_chats()
        await self.get_users()
        await self.get_blacklisted(True)
        await self.get_logger()
        logger.info("Database cache loaded.")
