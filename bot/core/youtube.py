"""V4-style yt-dlp YouTube resolver adapted to BikaMusic's legacy Track API.

Search, playlist, and download method signatures remain compatible with the
existing play/queue/voice handlers. Media files are downloaded only when the
existing playback flow calls download().
"""
import asyncio
import os
import random
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import aiohttp
import yt_dlp

from bot import logger
from bot.helpers import Track, utils


class YouTube:
    def __init__(self):
        self.watch_url = "https://www.youtube.com/watch?v="
        self.cookie_files = []
        self.cookies_loaded = False
        self.cookie_folder = "bot/cookies"
        self.cookie_warned = False
        self.download_dir = Path("downloads")
        self.download_dir.mkdir(parents=True, exist_ok=True)

        self.youtube_pattern = re.compile(
            r"^(?:https?://)?(?:(?:www|m|music)\\.)?"
            r"(?:youtube\\.com/(?:watch\\?v=|shorts/|playlist\\?list=)|youtu\\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)(?:[&?][^\\s]*)?$",
            re.IGNORECASE,
        )
        self.invalid_pattern = re.compile(
            r"^https?://(?:(?:www|m|music)\\.)?(?:youtube\\.com|youtu\\.be)"
            r"(?!/(?:watch\\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\\?list=PL[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11}))\\S*",
            re.IGNORECASE,
        )

    def load_cookies(self):
        if not self.cookies_loaded:
            if os.path.isdir(self.cookie_folder):
                self.cookie_files = sorted(
                    str(Path(self.cookie_folder) / name)
                    for name in os.listdir(self.cookie_folder)
                    if name.lower().endswith(".txt")
                    and (Path(self.cookie_folder) / name).is_file()
                )
            self.cookies_loaded = True

        if not self.cookie_files:
            if not self.cookie_warned:
                self.cookie_warned = True
                logger.warning("No YouTube cookies configured; trying without cookies.")
            return None
        return random.choice(self.cookie_files)

    async def save_cookies(self, cookie_urls: list[str]) -> None:
        """Download cookie files from the configured raw cookie-host URLs."""
        logger.info("Saving YouTube cookies...")
        Path(self.cookie_folder).mkdir(parents=True, exist_ok=True)
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for source_url in cookie_urls:
                file_name = source_url.rstrip("/").split("/")[-1]
                if not file_name or not re.fullmatch(r"[A-Za-z0-9_.-]+", file_name):
                    continue
                raw_url = "https://batbin.me/raw/" + file_name
                async with session.get(raw_url) as response:
                    response.raise_for_status()
                    content = await response.read()
                    if not content:
                        raise ValueError(f"Cookie source returned an empty file: {file_name}")
                    destination = Path(self.cookie_folder) / f"{file_name}.txt"
                    destination.write_bytes(content)
        self.cookie_files = []
        self.cookies_loaded = False
        logger.info("YouTube cookies saved in %s.", self.cookie_folder)

    def valid(self, url: str) -> bool:
        return bool(self.youtube_pattern.match(url or ""))

    def invalid(self, url: str) -> bool:
        return bool(self.invalid_pattern.match(url or ""))

    @staticmethod
    def _normalize_query(query: str) -> str:
        value = (query or "").strip()
        if not value:
            raise ValueError("Please provide a song name or YouTube URL.")
        if value.lower().startswith((
            "youtube.com/", "www.youtube.com/", "m.youtube.com/",
            "music.youtube.com/", "youtu.be/", "www.youtu.be/",
        )):
            value = "https://" + value
        parsed = urlparse(value)
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            raise ValueError("Only HTTP(S) media URLs are supported.")
        if parsed.netloc:
            host = (parsed.hostname or "").lower().rstrip(".")
            allowed = (
                host == "youtube.com" or host.endswith(".youtube.com")
                or host == "youtu.be" or host.endswith(".youtu.be")
            )
            if not allowed:
                raise ValueError("Only YouTube URLs are supported.")
        return value

    def _base_options(self, *, playlist: bool = False) -> dict:
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": not playlist,
            "socket_timeout": 20,
            "retries": 3,
            "fragment_retries": 3,
            "extractor_retries": 2,
        }
        cookie_file = self.load_cookies()
        if cookie_file and Path(cookie_file).is_file():
            options["cookiefile"] = cookie_file
        return options

    @staticmethod
    def _extract_info(query: str, options: dict) -> dict:
        with yt_dlp.YoutubeDL(options) as ydl:
            if query.startswith(("http://", "https://")):
                return ydl.extract_info(query, download=False)
            result = ydl.extract_info(f"ytsearch1:{query}", download=False)
            entries = (result or {}).get("entries") or []
            if not entries:
                return {}
            return entries[0]

    async def search(self, query: str, msg_id: int, video: bool = False) -> Track | None:
        try:
            value = self._normalize_query(query)
            info = await asyncio.to_thread(
                self._extract_info, value, self._base_options()
            )
            if not info:
                return None
            duration = int(info.get("duration") or 0)
            duration_text = utils.format_eta(duration) if duration else "00:00"
            webpage_url = info.get("webpage_url") or info.get("original_url")
            video_id = str(info.get("id") or "").strip()
            if not video_id and webpage_url:
                params = parse_qs(urlparse(webpage_url).query)
                video_id = (params.get("v") or [""])[0]
            if not video_id:
                return None
            return Track(
                id=video_id,
                channel_name=str(info.get("channel") or info.get("uploader") or "YouTube"),
                duration=duration_text,
                duration_sec=duration,
                message_id=msg_id,
                title=str(info.get("title") or "Unknown title")[:25],
                thumbnail=str(info.get("thumbnail") or "").split("?")[0] or None,
                url=str(webpage_url or f"{self.watch_url}{video_id}"),
                view_count=self._format_view_count(info.get("view_count")),
                video=video,
            )
        except Exception as exc:
            logger.warning("YouTube search/resolve failed (%s)", type(exc).__name__)
            return None

    @staticmethod
    def _format_view_count(value) -> str:
        try:
            count = int(value or 0)
        except (TypeError, ValueError):
            return ""
        if count < 0:
            return ""
        if count >= 1_000_000_000:
            return f"{count / 1_000_000_000:.1f}B views"
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M views"
        if count >= 1_000:
            return f"{count / 1_000:.1f}K views"
        return f"{count:,} views" if count else ""

    @staticmethod
    def _extract_playlist(query: str, limit: int, options: dict) -> list[dict]:
        options = {
            **options,
            "noplaylist": False,
            "extract_flat": "in_playlist",
            "ignoreerrors": True,
            "playlistend": limit,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            result = ydl.extract_info(query, download=False)
        return [item for item in ((result or {}).get("entries") or [])[:limit] if item]

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track]:
        try:
            value = self._normalize_query(url)
            entries = await asyncio.to_thread(
                self._extract_playlist,
                value,
                max(1, int(limit)),
                self._base_options(playlist=True),
            )
            tracks = []
            for item in entries:
                video_id = str(item.get("id") or "").strip()
                candidate = str(item.get("webpage_url") or item.get("url") or "").strip()
                if not video_id and candidate:
                    params = parse_qs(urlparse(candidate).query)
                    video_id = (params.get("v") or [""])[0]
                    if not video_id and "youtu.be/" in candidate:
                        video_id = urlparse(candidate).path.strip("/").split("/")[0]
                if not video_id:
                    continue
                duration = int(item.get("duration") or 0)
                tracks.append(Track(
                    id=video_id,
                    channel_name=str(item.get("channel") or item.get("uploader") or "YouTube"),
                    duration=utils.format_eta(duration) if duration else "00:00",
                    duration_sec=duration,
                    title=str(item.get("title") or "Unknown title")[:25],
                    thumbnail=str(item.get("thumbnail") or "").split("?")[0] or None,
                    url=candidate if candidate.startswith(("https://", "http://")) else f"{self.watch_url}{video_id}",
                    user=user,
                    view_count=self._format_view_count(item.get("view_count")),
                    video=video,
                ))
            return tracks
        except Exception as exc:
            logger.warning("YouTube playlist extraction failed (%s)", type(exc).__name__)
            return []

    def _download_sync(self, video_id: str, video: bool, cookie_file: str | None) -> str:
        url = self.watch_url + video_id
        template = str(self.download_dir / "%(id)s.%(ext)s")
        selector = (
            "(bestvideo[height<=?720][width<=?1280])+bestaudio/best[height<=?720]"
            if video else "bestaudio/best"
        )
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": selector,
            "outtmpl": template,
            "restrictfilenames": True,
            "socket_timeout": 30,
            "retries": 3,
            "fragment_retries": 3,
            "extractor_retries": 2,
            "overwrites": False,
        }
        if video:
            options["merge_output_format"] = "mp4"
        if cookie_file and Path(cookie_file).is_file():
            options["cookiefile"] = cookie_file

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            prepared = Path(ydl.prepare_filename(info))
            if prepared.is_file() and prepared.stat().st_size > 0:
                return str(prepared)

        candidates = sorted(
            (
                path for path in self.download_dir.glob(f"{video_id}.*")
                if path.is_file() and path.stat().st_size > 0
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return str(candidates[0])
        raise FileNotFoundError(f"yt-dlp did not produce a media file for {video_id}")

    async def download(self, video_id: str, video: bool = False) -> str | None:
        video_id = str(video_id or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            return None
        candidates = [
            path for path in self.download_dir.glob(f"{video_id}.*")
            if path.is_file() and path.stat().st_size > 0
        ]
        if candidates:
            return str(max(candidates, key=lambda path: path.stat().st_mtime))

        try:
            cookie_file = self.load_cookies()
            return await asyncio.to_thread(
                self._download_sync, video_id, video, cookie_file
            )
        except Exception as exc:
            logger.exception(
                "YouTube media download failed for %s (%s)",
                video_id,
                type(exc).__name__,
            )
            return None
