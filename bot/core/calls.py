
from ntgcalls import (
    ConnectionError,
    ConnectionNotFound,
    RTMPStreamingUnsupported,
    TelegramServerError,
)
from pyrogram.errors import (
    ChatSendMediaForbidden,
    ChatSendPhotosForbidden,
    MessageIdInvalid,
)
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

from bot import app, config, db, lang, logger, queue, thumb, userbot, yt
from bot.helpers import Media, Track, buttons


class TgCall(PyTgCalls):
    def __init__(self) -> None:
        self.active_clients = []

    async def pause_stream(self, chat_id: int) -> bool:
        assistant = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=True)
        return await assistant.pause(chat_id)

    async def resume_stream(self, chat_id: int) -> bool:
        assistant = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=False)
        return await assistant.resume(chat_id)

    async def stop_stream(self, chat_id: int) -> None:
        assistant = await db.get_assistant(chat_id)
        queue.clear(chat_id)
        await db.remove_call(chat_id)
        await db.set_loop(chat_id, 0)

        try:
            await assistant.leave_call(chat_id, close=False)
        except Exception:
            pass

    async def stream_media(
        self,
        chat_id: int,
        status_message: Message,
        media: Media | Track,
        seek_time: int = 0,
    ) -> None:
        assistant = await db.get_assistant(chat_id)
        chat_lang = await lang.get_lang(chat_id)

        preview = None
        if config.THUMB_GEN:
            preview = (
                await thumb.generate(media)
                if isinstance(media, Track)
                else config.DEFAULT_THUMB
            )

        if not media.file_path:
            await status_message.edit_text(
                chat_lang["error_no_file"].format(config.SUPPORT_CHAT)
            )
            return await self.play_next(chat_id)

        stream = types.MediaStream(
            media_path=media.file_path,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if media.video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=f"-ss {seek_time}" if seek_time > 1 else None,
        )

        try:
            await assistant.play(
                chat_id=chat_id,
                stream=stream,
                config=types.GroupCallConfig(auto_start=False),
            )

            if not seek_time:
                media.time = 1
                await db.add_call(chat_id)

                text = chat_lang["play_media"].format(
                    media.url,
                    media.title,
                    media.duration,
                    media.user,
                )
                keyboard = buttons.controls(chat_id)

                try:
                    if preview:
                        await status_message.edit_media(
                            media=InputMediaPhoto(
                                media=preview,
                                caption=text,
                            ),
                            reply_markup=keyboard,
                        )
                    else:
                        await status_message.edit_text(text, reply_markup=keyboard)
                except (
                    ChatSendMediaForbidden,
                    ChatSendPhotosForbidden,
                    MessageIdInvalid,
                ):
                    if preview:
                        sent = await app.send_photo(
                            chat_id=chat_id,
                            photo=preview,
                            caption=text,
                            reply_markup=keyboard,
                        )
                    else:
                        sent = await app.send_message(
                            chat_id=chat_id,
                            text=text,
                            reply_markup=keyboard,
                        )
                    media.message_id = sent.id

        except FileNotFoundError:
            await status_message.edit_text(
                chat_lang["error_no_file"].format(config.SUPPORT_CHAT)
            )
            await self.play_next(chat_id)

        except exceptions.NoActiveGroupCall:
            await self.stop_stream(chat_id)
            await status_message.edit_text(chat_lang["error_no_call"])

        except exceptions.NoAudioSourceFound:
            await status_message.edit_text(chat_lang["error_no_audio"])
            await self.play_next(chat_id)

        except (ConnectionError, ConnectionNotFound, TelegramServerError):
            await self.stop_stream(chat_id)
            await status_message.edit_text(chat_lang["error_tg_server"])

        except RTMPStreamingUnsupported:
            await self.stop_stream(chat_id)
            await status_message.edit_text(chat_lang["error_rtmp"])

    async def replay_current(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return

        current = queue.get_current(chat_id)
        chat_lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=chat_lang["play_again"])
        current.message_id = msg.id
        await self.stream_media(chat_id, msg, current)

    async def play_next(self, chat_id: int) -> None:
        loop_count = await db.get_loop(chat_id)
        if loop_count:
            await db.set_loop(chat_id, loop_count - 1)
            return await self.replay_current(chat_id)

        next_media = queue.get_next(chat_id)

        try:
            if next_media and next_media.message_id:
                await app.delete_messages(
                    chat_id=chat_id,
                    message_ids=next_media.message_id,
                    revoke=True,
                )
                next_media.message_id = 0
        except Exception:
            pass

        if not next_media:
            return await self.stop_stream(chat_id)

        chat_lang = await lang.get_lang(chat_id)
        msg = await app.send_message(chat_id=chat_id, text=chat_lang["play_next"])

        if not next_media.file_path:
            next_media.file_path = await yt.download(
                next_media.id,
                video=next_media.video,
            )
            if not next_media.file_path:
                await self.play_next(chat_id)
                return await msg.edit_text(
                    chat_lang["error_no_file"].format(config.SUPPORT_CHAT)
                )

        next_media.message_id = msg.id
        await self.stream_media(chat_id, msg, next_media)

    async def ping(self) -> float:
        ping_values = [client.ping for client in self.active_clients]
        return round(sum(ping_values) / len(ping_values), 2)

    async def register_handlers(self, client: PyTgCalls) -> None:
        @client.on_update()
        async def call_update(_, update: types.Update) -> None:
            if isinstance(update, types.StreamEnded):
                if update.stream_type == types.StreamEnded.Type.AUDIO:
                    await self.play_next(update.chat_id)

            elif isinstance(update, types.ChatUpdate):
                if update.status in (
                    types.ChatUpdate.Status.KICKED,
                    types.ChatUpdate.Status.LEFT_GROUP,
                    types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                ):
                    await self.stop_stream(update.chat_id)

    async def boot(self) -> None:
        PyTgCallsSession.notice_displayed = True

        for assistant_client in userbot.clients:
            call_client = PyTgCalls(assistant_client, cache_duration=100)
            await call_client.start()
            self.active_clients.append(call_client)
            await self.register_handlers(call_client)

        logger.info("PyTgCalls clients started successfully.")
