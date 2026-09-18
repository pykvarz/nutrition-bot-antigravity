import os
import asyncio
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.services.sheets_service import SheetsService
from bot.services.gemini_service import GeminiService
from bot.services.groq_service import GroqService
from bot.services.nutrition_service import NutritionService
from bot.handlers.domain import DomainHandler
from bot.handlers.router import create_bot_router

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nutrition_bot_polling")


async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is missing in .env")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    sheets = SheetsService()
    gemini = GeminiService()
    groq = GroqService()
    nutrition = NutritionService()

    domain = DomainHandler(sheets_service=sheets, nutrition_service=nutrition)
    router = create_bot_router(domain_handler=domain, gemini_service=gemini, groq_service=groq)

    dp = Dispatcher()
    dp.include_router(router)

    logger.info("Удаление старых webhook перед запуском polling...")
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Бот успешно запущен в режиме локального тестирования! Ожидание сообщений в Telegram...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
