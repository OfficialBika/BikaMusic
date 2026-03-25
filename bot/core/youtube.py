import asyncio
import os
import random
import re
from pathlib import Path

import aiohttp
import yt_dlp
from py_yt import Playlist, VideosSearch

from bot import logger
from bot.helpers import Track, utils


class YouTube:
    def __init__(self):
        self.watch_url = "https://www.youtube.com/watch?v="
        self.cookie_files = []
        self.cookies_loaded = False
        self.cookie_folder = "bot/cookies"
        self.cookie_warned = False

        self.youtube_pattern = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self.invalid_pattern = re.compile(
            r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)"
            r"(?!/(watch\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\?list=PL[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11}))\S*"
        )

    def load_cookies(self):
        if not self.cookies_loaded:
            if os.path.isdir(self.cookie_folder):
                for file_name in os.listdir(self.cookie_folder):
                    if file_name.endswith(".txt"):
                        self.cookie_files.append(f"{self.cookie_folder}/{file_name}")
            self.cookies_loaded = True

        if not self.cookie_files:
            if not self.cookie_warned:
                self.cookie_warned = True
                logger.warning("Cookies are missing; downloads might fail.")
            return None

        return random.choice(self.cookie_files)

    async def save_cookies(self, cookie_urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")

        async with aiohttp.ClientSession() as session:
            for source_url in cookie_urls:
                file_name = source_url.split("/")[-1]
                raw_url = "https://batbin.me/raw/" + file_name

                async with session.get(raw_url) as response:
                    response.raise_for_status()
                    with open(f"{self.cookie_folder}/{file_name}.txt", "wb") as fw:
                        fw.write(await response.read())

        logger.info("Cookies saved in %s.", self.cookie_folder)

    def valid(self, url: str) -> bool:
        return bool(re.match(self.youtube_pattern, url))

    def invalid(self, url: str) -> bool:
        return bool(re.match(self.invalid_pattern, url))

    async def search(
        self,
        query: str,
        msg_id: int,
        video: bool = False,
    ) -> Track | None:
        try:
            searcher = VideosSearch(query, limit=1, with_live=False)
            result = await searcher.next()
        except Exception:
            return None

        if result and result["result"]:
            data = result["result"][0]
            return Track(
                id=data.get("id"),
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=msg_id,
                title=data.get("title")[:25],
                thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )

        return None

    async def playlist(
        self,
        limit: int,
        user: str,
        url: str,
        video: bool,
    ) -> list[Track | None]:
        playlist_tracks = []

        try:
            playlist_data = await Playlist.get(url)
            for item in playlist_data["videos"][:limit]:
                playlist_tracks.append(
                    Track(
                        id=item.get("id"),
                        channel_name=item.get("channel", {}).get("name", ""),
                        duration=item.get("duration"),
                        duration_sec=utils.to_seconds(item.get("duration")),
                        title=item.get("title")[:25],
                        thumbnail=item.get("thumbnails")[-1]
                        .get("url")
                        .split("?")[0],
                        url=item.get("link").split("&list=")[0],
                        user=user,
                        view_count="",
                        video=video,
                    )
                )
        except Exception:
            pass

        return playlist_tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        url = self.watch_url + video_id
        extension = "mp4" if video else "webm"
        output_file = f"downloads/{video_id}.{extension}"

        if Path(output_file).exists():
            return output_file

        cookie_file = self.load_cookies()

        common_options = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            "cookiefile": cookie_file,
        }

        if video:
            ydl_options = {
                **common_options,
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio)",
                "merge_output_format": "mp4",
            }
        else:
            ydl_options = {
                **common_options,
                "format": "bestaudio[ext=webm][acodec=opus]",
            }

        def _run_download():
            with yt_dlp.YoutubeDL(ydl_options) as ydl:
                try:
                    ydl.download([url])
                except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError):
                    return None
                except Exception as exc:
                    logger.warning("Download failed: %s", exc)
                    return None
            return output_file

        return await asyncio.to_thread(_run_download)
