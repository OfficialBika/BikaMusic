import asyncio
from yt_dlp import YoutubeDL

YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "geo_bypass": True,
    "default_search": "ytsearch1",
}

async def search_youtube(query: str):
    loop = asyncio.get_event_loop()

    def _extract():
        with YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return {
                "title": info.get("title", "Unknown Title"),
                "url": info.get("url"),
                "webpage_url": info.get("webpage_url"),
                "duration": info.get("duration", 0),
            }

    return await loop.run_in_executor(None, _extract)
