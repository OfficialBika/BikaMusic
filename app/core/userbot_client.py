from pyrogram import Client
from config import API_ID, API_HASH, SESSION_STRING

assistant = Client(
    "bika_music_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)
