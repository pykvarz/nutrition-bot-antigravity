import os
import sys
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")


async def set_webhook():
    if not TELEGRAM_BOT_TOKEN:
        print("Ошибка: TELEGRAM_BOT_TOKEN не задан в .env")
        sys.exit(1)
    if not WEBHOOK_URL:
        print("Ошибка: WEBHOOK_URL не задан в .env")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    payload = {
        "url": WEBHOOK_URL,
        "allowed_updates": ["message", "callback_query"],
    }
    if TELEGRAM_WEBHOOK_SECRET:
        payload["secret_token"] = TELEGRAM_WEBHOOK_SECRET

    print(f"Установка webhook на {WEBHOOK_URL}...")
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if data.get("ok"):
                print("Webhook успешно установлен!")
                print(data)
            else:
                print("Ошибка установки webhook:")
                print(data)


if __name__ == "__main__":
    asyncio.run(set_webhook())
