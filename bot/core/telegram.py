import asyncio
import os
import time

from pyrogram import types

from bot import config
from bot.helpers import Media, buttons, utils


class Telegram:
    def __init__(self):
        self.active_downloads = []
        self.cancel_events = {}
        self.last_updates = {}
        self.download_tasks = {}
        self.edit_sleep = 5

    def has_media(self, message: types.Message) -> bool:
        return any([message.video, message.audio, message.document, message.voice])

    async def cancel(self, query: types.CallbackQuery):
        msg_id = query.message.id
        event = self.cancel_events.get(msg_id)
        task = self.download_tasks.pop(msg_id, None)

        if event:
            event.set()

        if task and not task.done():
            task.cancel()

        if event or task:
            await query.edit_message_text(
                query.lang["dl_cancel"].format(query.from_user.mention)
            )
        else:
            await query.answer(query.lang["dl_not_found"], show_alert=True)

    async def download(
        self,
        message: types.Message,
        status_message: types.Message,
    ) -> Media | None:
        status_id = status_message.id
        cancel_event = asyncio.Event()

        self.cancel_events[status_id] = cancel_event
        self.last_updates[status_id] = 0

        started_at = time.time()

        media = (
            message.audio
            or message.voice
            or message.video
            or message.document
        )

        file_id = getattr(media, "file_unique_id", None)
        file_name = getattr(media, "file_name", "") or ""
        file_ext = file_name.split(".")[-1] if "." in file_name else "bin"
        file_size = getattr(media, "file_size", 0)
        file_title = getattr(media, "title", "Telegram File") or "Telegram File"
        duration = getattr(media, "duration", 0)
        is_video = bool(getattr(media, "mime_type", "").startswith("video/"))

        if duration > config.DURATION_LIMIT:
            await status_message.edit_text(
                status_message.lang["play_duration_limit"].format(
                    config.DURATION_LIMIT // 60
                )
            )
            return await status_message.stop_propagation()

        if file_size > 200 * 1024 * 1024:
            await status_message.edit_text(status_message.lang["dl_limit"])
            return await status_message.stop_propagation()

        async def progress(current, total):
            if cancel_event.is_set():
                return

            now = time.time()
            if now - self.last_updates[status_id] < self.edit_sleep:
                return

            self.last_updates[status_id] = now

            percent = current * 100 / total
            speed = current / (now - started_at or 1e-6)
            eta = utils.format_eta(int((total - current) / speed))

            text = status_message.lang["dl_progress"].format(
                utils.format_size(current),
                utils.format_size(total),
                percent,
                utils.format_size(speed),
                eta,
            )

            await status_message.edit_text(
                text,
                reply_markup=buttons.cancel_dl(status_message.lang["cancel"]),
            )

        try:
            save_path = f"downloads/{file_id}.{file_ext}"

            if not os.path.exists(save_path):
                if file_id in self.active_downloads:
                    await status_message.edit_text(status_message.lang["dl_active"])
                    return await status_message.stop_propagation()

                self.active_downloads.append(file_id)

                task = asyncio.create_task(
                    message.download(
                        file_name=save_path,
                        progress=progress,
                    )
                )
                self.download_tasks[status_id] = task
                await task

                if file_id in self.active_downloads:
                    self.active_downloads.remove(file_id)

                self.download_tasks.pop(status_id, None)

                await status_message.edit_text(
                    status_message.lang["dl_complete"].format(
                        round(time.time() - started_at, 2)
                    )
                )

            return Media(
                id=file_id,
                duration=time.strftime("%M:%S", time.gmtime(duration)),
                duration_sec=duration,
                file_path=save_path,
                message_id=status_message.id,
                url=message.link,
                title=file_title[:25],
                video=is_video,
            )

        except asyncio.CancelledError:
            return await status_message.stop_propagation()

        finally:
            self.cancel_events.pop(status_id, None)
            self.last_updates.pop(status_id, None)

            if file_id in self.active_downloads:
                self.active_downloads.remove(file_id)

    async def process_m3u8(self, url: str, msg_id: int, video: bool) -> Media:
        return Media(
            id=str(msg_id),
            file_path=url,
            message_id=msg_id,
            url=url,
            title="M3U8 Stream",
            video=video,
                          )
