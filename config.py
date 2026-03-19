import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

BOT_NAME = os.getenv("BOT_NAME", "BIKA Music Bot")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "0"))

if not API_ID:
    raise ValueError("Missing API_ID in .env")
if not API_HASH:
    raise ValueError("Missing API_HASH in .env")
if not BOT_TOKEN:
    raise ValueError("Missing BOT_TOKEN in .env")
if not SESSION_STRING:
    raise ValueError("Missing SESSION_STRING in .env")
