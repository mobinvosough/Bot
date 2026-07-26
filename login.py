from pyrogram import Client
from config import settings

app = Client(
    name="content_forward_bot",
    api_id=settings.API_ID,
    api_hash=settings.API_HASH,
    phone_number=settings.PHONE_NUMBER,
)

app.run()
print("Login successful. Session saved.")
