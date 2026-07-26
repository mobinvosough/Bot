import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from pyrogram import Client

PHONE = os.getenv("PHONE_NUMBER", "")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

if not PHONE or not API_ID or not API_HASH:
    print("Error: PHONE_NUMBER, API_ID, API_HASH must be set in .env")
    sys.exit(1)

app = Client(
    name="content_forward_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    phone_number=PHONE,
)

app.run()
print("Login successful. Session saved.")
