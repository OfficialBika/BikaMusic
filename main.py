# main.py
# ==========================================
# BikaMusic — Group Voice Chat Music Bot (Render Free)
# - Python 3.11
# - Webhook (FastAPI)
# - /health endpoint (UptimeRobot)
# - MongoDB ready (Motor)
# - VC Streaming via Assistant User (Pyrogram + PyTgCalls)
#
# ENV required:
#   BOT_TOKEN
#   PUBLIC_URL                  e.g. https://bikamusic.onrender.com
#   WEBHOOK_PATH                e.g. /telegram   (optional, default /telegram)
#   WEBHOOK_SECRET              (optional but recommended)
#   API_ID
#   API_HASH
#   SESSION_STRING              (Pyrogram session for assistant user)
#   MONGODB_URI
#
# Optional:
#   ASSISTANT_USERNAME          default @BikaAssistant
#   PORT                        default 10000 (Render supplies)
# ==========================================

import os
import re
import asyncio
import subprocess
from typing import Dict, List, Optional

import imageio_ffmpeg  # ffmpeg binary helper (Render-friendly)

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse

from motor.motor_asyncio import AsyncIOMotorClient

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, Update
from aiogram.client.default import DefaultBotProperties

from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types.input_stream import InputStream, AudioPiped


# ----------------------------
# ENV
# ----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PUBLIC_URL = os.getenv("PUBLIC_URL", "").strip().rstrip("/")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/telegram").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()  # optional

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
PORT = int(os.getenv("PORT", "10000"))

ASSISTANT_USERNAME = os.getenv("ASSISTANT_USERNAME", "@BikaAssistant").strip()
ASSISTANT_USERNAME = (
    ASSISTANT_USERNAME if ASSISTANT_USERNAME.startswith("@") else f"@{ASSISTANT_USERNAME}"
)
ASSISTANT_LINK = f"https://t.me/{ASSISTANT_USERNAME[1:]}"

# small sanity-check so Render မှာ log ကြည့်လို့ လွယ်အောင်
missing: List[str] = []
if not BOT_TOKEN:
    missing.append("BOT_TOKEN")
if not PUBLIC_URL:
    missing.append("PUBLIC_URL")
if not API_ID:
    missing.append("API_ID")
if not API_HASH:
    missing.append("API_HASH")
if not SESSION_STRING:
    missing.append("SESSION_STRING")
if not MONGODB_URI:
    missing.append("MONGODB_URI")

if missing:
    raise RuntimeError(f"Missing env vars: {', '.join(missing)}")


# ----------------------------
# DB (ready for future settings)
# ----------------------------
mongo = AsyncIOMotorClient(MONGODB_URI)
db = mongo["telegram_music_bot"]
col_settings = db["settings"]  # reserved (dj mode, volume, etc.)


# ----------------------------
# Telegram Bot (Webhook) via aiogram
# ----------------------------
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()


# ----------------------------
# Assistant (userbot) + PyTgCalls for VC streaming
# ----------------------------
assistant = Client(
    "assistant",
    session_string=SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH,
)

calls = PyTgCalls(assistant)

ASSISTANT_ID: Optional[int] = None  # set on startup

# In-memory queue (simple, fast)
mem_queue: Dict[int, List[str]] = {}  # chat_id -> [file_path, ...]
mem_now: Dict[int, Optional[str]] = {}  # chat_id -> current file path


# ----------------------------
# Helpers
# ----------------------------
def normalize_music_query(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def safe_basename(path: Optional[str]) -> str:
    if not path:
        return "—"
    return os.path.basename(path).replace("<", "").replace(">", "")


def ytdlp_to_mp3(query_or_url: str) -> str:
    """
    Download best audio and convert to mp3 into /tmp, return file path.
    Requires: yt-dlp + ffmpeg installed.
    """
    os.makedirs("/tmp/tg_music", exist_ok=True)
    outtmpl = "/tmp/tg_music/%(title).80s_%(id)s.%(ext)s"

    target = query_or_url
    if not is_url(query_or_url):
        target = f"ytsearch1:{query_or_url}"

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format",
        "mp3",
        "--no-playlist",
        "-o",
        outtmpl,
        target,
    ]
    subprocess.check_call(cmd)

    files = [f for f in os.listdir("/tmp/tg_music") if f.endswith(".mp3")]
    files.sort(key=lambda x: os.path.getmtime(os.path.join("/tmp/tg_music", x)), reverse=True)
    if not files:
        raise RuntimeError("No mp3 produced")
    return os.path.join("/tmp/tg_music", files[0])


async def cleanup_file(path: str):
    try:
        os.remove(path)
    except Exception:
        pass


async def ensure_peer(chat_id: int):
    """
    VERY IMPORTANT:
    Pyrogram/PyTgCalls ကို group peer ကိုသိအောင် preload လုပ်ပေးတာ။
    ဒီဟာ မလုပ်ရင် 'Peer id invalid' / 'ID not found' error ပေါက်ပြီး
    service shutdown သွားနိုင်တယ်။
    """
    try:
        await assistant.get_chat(chat_id)
    except Exception:
        # group မရှိရင် / missing permissions ဖြစ်ရင် ဒီနေရာမှာပဲ later handle
        pass


async def assistant_in_group(chat_id: int) -> bool:
    """
    Check if assistant user account is a member of the group.
    """
    global ASSISTANT_ID
    if not ASSISTANT_ID:
        return False
    try:
        await ensure_peer(chat_id)
        await assistant.get_chat_member(chat_id, ASSISTANT_ID)
        return True
    except Exception:
        return False


async def ensure_join_and_play(chat_id: int, file_path: str):
    """
    Join VC if not joined; otherwise change stream.
    Peer preload + safe join/change to avoid crash.
    """
    await ensure_peer(chat_id)

    try:
        # already joined -> just change stream
        await calls.change_stream(chat_id, InputStream(AudioPiped(file_path)))
    except Exception:
        # not joined yet -> join group call
        await calls.join_group_call(chat_id, InputStream(AudioPiped(file_path)))


async def play_next(chat_id: int):
    """
    Play first item in queue; if empty -> leave VC.
    """
    q = mem_queue.get(chat_id, [])
    if not q:
        mem_now[chat_id] = None
        try:
            await calls.leave_group_call(chat_id)
        except Exception:
            pass
        return

    file_path = q[0]
    mem_now[chat_id] = file_path
    await ensure_join_and_play(chat_id, file_path)


# ----------------------------
# Commands
# ----------------------------
@dp.message(Command("start"))
async def cmd_start(m: Message):
    txt = (
        "🎵 <b>Bika Music — Group Voice Chat Music Bot</b>\n\n"
        "Commands:\n"
        "• <code>/setup</code> — setup guide\n"
        "• <code>/status</code> — စစ်ဆေးရန်\n"
        "• <code>/play MusicName</code> — VC ထဲ stream\n"
        "• <code>/play URL</code> — URL stream\n"
        "• <code>/skip</code> — နောက်တစ်ပုဒ်\n"
        "• <code>/stop</code> — ရပ် + queue ဖျက်\n"
        "• <code>/queue</code> — စာရင်းကြည့်\n\n"
        "⚠️ Voice Chat ကို အရင်ဖွင့်ထားရမယ်\n"
        f"ℹ️ Assistant: <a href=\"{ASSISTANT_LINK}\">{ASSISTANT_USERNAME}</a> ကို group ထဲ add/invite လုပ်ထားပါ"
    )
    await m.reply(txt, disable_web_page_preview=True)


@dp.message(Command("setup"))
async def cmd_setup(m: Message):
    if not m.chat or m.chat.type not in ("group", "supergroup"):
        return await m.reply("ဒီ command ကို group ထဲမှာပဲ သုံးပါ")

    txt = (
        "🛠 <b>Setup (Group Voice Chat)</b>\n\n"
        "1) Group ထဲမှာ <b>Voice Chat</b> ကို ဖွင့်ပါ\n"
        f"2) Assistant account ကို group ထဲ add/invite လုပ်ပါ: <a href=\"{ASSISTANT_LINK}\">{ASSISTANT_USERNAME}</a>\n"
        "3) ပြီးရင် <code>/play songname</code> သုံးပါ\n\n"
        "📌 Note: Bot က user account ကို auto-add မလုပ်နိုင်ပါ (Telegram limitation)"
    )
    await m.reply(txt, disable_web_page_preview=True)


@dp.message(Command("status"))
async def cmd_status(m: Message):
    if not m.chat or m.chat.type not in ("group", "supergroup"):
        return await m.reply("ဒီ command ကို group ထဲမှာပဲ သုံးပါ")

    in_group = await assistant_in_group(m.chat.id)
    q = mem_queue.get(m.chat.id, [])
    now = mem_now.get(m.chat.id)

    txt = (
        "🔎 <b>Status</b>\n"
        f"• Assistant in group: {'✅ Yes' if in_group else '❌ No'}\n"
        f"• Queue length: <b>{len(q)}</b>\n"
        f"• Now playing: <code>{safe_basename(now)}</code>\n"
    )

    if not in_group:
        txt += (
            "\n➡️ Assistant ကို group ထဲ add လုပ်ပါ:\n"
            f"• <a href=\"{ASSISTANT_LINK}\">{ASSISTANT_USERNAME}</a>\n"
            "ပြီးရင် Voice Chat ဖွင့်ပြီး /play သုံးပါ။"
        )

    await m.reply(txt, disable_web_page_preview=True)


@dp.message(Command("play"))
async def cmd_play(m: Message):
    if not m.chat or m.chat.type not in ("group", "supergroup"):
        return await m.reply("VC stream က group/supergroup ထဲမှာပဲ သုံးပါ")

    parts = (m.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await m.reply("အသုံးပြုပုံ: <code>/play MusicName</code> သို့ <code>/play URL</code>")

    # assistant presence check BEFORE downloading (saves CPU/time)
    if not await assistant_in_group(m.chat.id):
        return await m.reply(
            "❌ Assistant account မရှိသေးပါ။\n\n"
            f"➡️ Add/Invite: <a href=\"{ASSISTANT_LINK}\">{ASSISTANT_USERNAME}</a>\n"
            "✅ ပြီးရင် Voice Chat ဖွင့်ပြီး /play ပြန်ခေါ်ပါ",
            disable_web_page_preview=True,
        )

    query = normalize_music_query(parts[1])
    msg = await m.reply("🔎 ရှာ/ဖော်ထုတ်နေပါတယ်…")

    try:
        file_path = await asyncio.to_thread(ytdlp_to_mp3, query)
    except Exception as e:
        return await msg.edit_text(f"❌ မရပါ: <code>{str(e)[:180]}</code>")

    mem_queue.setdefault(m.chat.id, []).append(file_path)

    if len(mem_queue[m.chat.id]) == 1:
        try:
            await play_next(m.chat.id)
            await msg.edit_text(f"▶️ Playing: <code>{safe_basename(file_path)}</code>")
        except Exception as e:
            await msg.edit_text(
                "⚠️ VC join/play မရပါ\n"
                f"• Error: <code>{str(e)[:180]}</code>\n\n"
                "✅ စစ်ရန်:\n"
                "1) Voice Chat ဖွင့်ထားလား\n"
                "2) Assistant account ကို group ထဲ add ထားလား\n"
                "3) Bot/assistant ကို VC join လုပ်ခွင့်ရှိလား"
            )
    else:
        await msg.edit_text(f"➕ Queued: <code>{safe_basename(file_path)}</code>")


@dp.message(Command("skip"))
async def cmd_skip(m: Message):
    if not m.chat or m.chat.type not in ("group", "supergroup"):
        return await m.reply("ဒီ command ကို group ထဲမှာပဲ သုံးပါ")

    q = mem_queue.get(m.chat.id, [])
    if not q:
        return await m.reply("Queue မရှိပါ")

    cur = q.pop(0)
    await cleanup_file(cur)

    if not q:
        mem_now[m.chat.id] = None
        try:
            await calls.leave_group_call(m.chat.id)
        except Exception:
            pass
        return await m.reply("⏹ Stopped (queue empty)")

    try:
        await play_next(m.chat.id)
        await m.reply("⏭ Skipped")
    except Exception as e:
        await m.reply(f"⚠️ Next play မရ: <code>{str(e)[:180]}</code>")


@dp.message(Command("stop"))
async def cmd_stop(m: Message):
    if not m.chat or m.chat.type not in ("group", "supergroup"):
        return await m.reply("ဒီ command ကို group ထဲမှာပဲ သုံးပါ")

    q = mem_queue.get(m.chat.id, [])
    for f in q:
        await cleanup_file(f)

    mem_queue[m.chat.id] = []
    mem_now[m.chat.id] = None

    try:
        await calls.leave_group_call(m.chat.id)
    except Exception:
        pass

    await m.reply("⏹ Stopped & cleared queue")


@dp.message(Command("queue"))
async def cmd_queue(m: Message):
    if not m.chat or m.chat.type not in ("group", "supergroup"):
        return await m.reply("ဒီ command ကို group ထဲမှာပဲ သုံးပါ")

    q = mem_queue.get(m.chat.id, [])
    if not q:
        return await m.reply("Queue မရှိပါ")

    lines = ["🎶 <b>Queue</b> (Top 20)"]
    for i, p in enumerate(q[:20], 1):
        prefix = "▶️ " if i == 1 else "• "
        lines.append(f"{prefix}{i}. <code>{safe_basename(p)}</code>")
    await m.reply("\n".join(lines))


# ----------------------------
# FastAPI (Webhook + Health)
# ----------------------------
app = FastAPI()


@app.get("/health")
async def health_get():
    return JSONResponse({"ok": True})


@app.head("/health")
async def health_head():
    # UptimeRobot HEAD request တွေ 405 ပို့မလို့ simple 200 respond
    return PlainTextResponse("", status_code=200)


@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    # Optional secret header validation (recommended)
    if WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != WEBHOOK_SECRET:
            return PlainTextResponse("forbidden", status_code=403)

    data = await request.json()

    try:
        update = Update.model_validate(data)  # aiogram v3 (pydantic)
        await dp.feed_update(bot, update)
    except Exception:
        # don't crash webhook
        pass

    return PlainTextResponse("ok")


# ----------------------------
# Startup / Shutdown
# ----------------------------
@app.on_event("startup")
async def on_startup():
    global ASSISTANT_ID

    # start assistant + calls
    await assistant.start()
    try:
        me = await assistant.get_me()
        ASSISTANT_ID = me.id
    except Exception:
        ASSISTANT_ID = None

    await calls.start()

    # set webhook
    webhook_url = f"{PUBLIC_URL}{WEBHOOK_PATH}"
    try:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None,
            drop_pending_updates=True,
        )
    except TelegramBadRequest:
        # ignore if already set or render reboots
        pass

    print("main.py loaded successfully")


@app.on_event("shutdown")
async def on_shutdown():
    # cleanup local tmp files best-effort
    try:
        for chat_id, items in list(mem_queue.items()):
            for f in items:
                await cleanup_file(f)
            mem_queue[chat_id] = []
            mem_now[chat_id] = None
    except Exception:
        pass

    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception:
        pass

    try:
        await calls.stop()
    except Exception:
        pass

    try:
        await assistant.stop()
    except Exception:
        pass

    try:
        await bot.session.close()
    except Exception:
        pass
