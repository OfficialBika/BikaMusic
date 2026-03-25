
import os

import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from bot import config
from bot.helpers import Track


class Thumbnail:
    def __init__(self):
        self.rect = (914, 514)
        self.fill = (255, 255, 255)
        self.mask = Image.new("L", self.rect, 0)
        self.font1 = ImageFont.truetype("bot/helpers/Raleway-Bold.ttf", 30)
        self.font2 = ImageFont.truetype("bot/helpers/Inter-Light.ttf", 30)
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        await self.session.close()

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with self.session.get(url) as response:
            with open(output_path, "wb") as file:
                file.write(await response.read())
        return output_path

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            temp_path = f"cache/temp_{song.id}.jpg"
            output_path = f"cache/{song.id}.png"

            if os.path.exists(output_path):
                return output_path

            await self.save_thumb(temp_path, song.thumbnail)

            thumb = Image.open(temp_path).convert("RGBA").resize(
                size,
                Image.Resampling.LANCZOS,
            )
            blurred = thumb.filter(ImageFilter.GaussianBlur(25))
            image = ImageEnhance.Brightness(blurred).enhance(0.40)

            rect = ImageOps.fit(
                thumb,
                self.rect,
                method=Image.LANCZOS,
                centering=(0.5, 0.5),
            )

            ImageDraw.Draw(self.mask).rounded_rectangle(
                (0, 0, self.rect[0], self.rect[1]),
                radius=15,
                fill=255,
            )
            rect.putalpha(self.mask)
            image.paste(rect, (183, 30), rect)

            draw = ImageDraw.Draw(image)
            draw.text(
                xy=(50, 560),
                text=f"{song.channel_name[:25]} | {song.view_count}",
                font=self.font2,
                fill=self.fill,
            )
            draw.text(
                (50, 600),
                song.title[:50],
                font=self.font1,
                fill=self.fill,
            )
            draw.text((40, 650), "0:01", font=self.font1)
            draw.line(
                [(140, 670), (1160, 670)],
                fill=self.fill,
                width=5,
                joint="curve",
            )
            draw.text((1185, 650), song.duration, font=self.font1, fill=self.fill)

            image.save(output_path)

            try:
                os.remove(temp_path)
            except Exception:
                pass

            return output_path

        except Exception:
            return config.DEFAULT_THUMB
