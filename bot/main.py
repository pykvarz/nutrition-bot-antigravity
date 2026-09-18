import os
import logging
from typing import Optional
from aiohttp import web
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
from bot.utils.dates import calculate_food_date

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nutrition_bot")


def create_app(
    sheets_service: Optional[SheetsService] = None,
    gemini_service: Optional[GeminiService] = None,
    groq_service: Optional[GroqService] = None,
    nutrition_service: Optional[NutritionService] = None,
    bot: Optional[Bot] = None,
    dp: Optional[Dispatcher] = None,
    webhook_secret: Optional[str] = None,
    allowed_user_id: Optional[int] = None,
) -> web.Application:
    """
    Фабрика приложения aiohttp. Поддерживает dependency injection для изолированного тестирования.
    """
    secret = webhook_secret or os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    target_user_id = allowed_user_id or int(os.getenv("ALLOWED_TELEGRAM_USER_ID", "0"))
    scheduler_token = os.getenv("SCHEDULER_SECRET", "")

    sheets = sheets_service or SheetsService()
    gemini = gemini_service or GeminiService()
    groq = groq_service or GroqService()
    nutrition = nutrition_service or NutritionService()

    domain = DomainHandler(sheets_service=sheets, nutrition_service=nutrition)
    router = create_bot_router(
        domain_handler=domain,
        gemini_service=gemini,
        groq_service=groq,
        allowed_user_id=target_user_id,
    )

    if dp is None:
        dp = Dispatcher()
        dp.include_router(router)

    app = web.Application()

    # 1. Healthcheck
    async def healthcheck(request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    # 2. Telegram Webhook
    async def handle_webhook(request: web.Request) -> web.Response:
        # Валидация секретного токена вебхука
        if secret:
            token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if token != secret:
                logger.warning("Rejected webhook request with invalid secret token.")
                return web.Response(status=403, text="Forbidden")

        try:
            update_data = await request.json()
        except Exception as e:
            logger.error(f"Failed to parse webhook JSON: {e}")
            return web.Response(status=400, text="Invalid JSON")

        update_id = update_data.get("update_id")
        if update_id is None:
            return web.Response(status=400, text="Missing update_id")

        # Инвариант 9: проверка идемпотентности ДО бизнес-логики
        if await sheets.is_update_processed(update_id):
            logger.info(f"Update {update_id} already processed. Skipping.")
            return web.json_response({"ok": True})

        if bot:
            try:
                await dp.feed_raw_update(bot, update_data)
            except Exception as e:
                logger.error(f"Error during update dispatching: {e}", exc_info=True)

        await sheets.mark_update_processed(update_id)
        return web.json_response({"ok": True})

    # 3. Cloud Scheduler: Напоминание
    async def job_reminder(request: web.Request) -> web.Response:
        if scheduler_token:
            token = request.headers.get("X-Scheduler-Token") or request.query.get("token")
            if token != scheduler_token:
                return web.Response(status=403, text="Forbidden")

        has_food = await sheets.has_food_record_in_last_hours(5.0)
        if has_food:
            return web.json_response({"status": "skipped", "reason": "recent_food"})

        has_recent_reminder = await sheets.has_recent_action("REMINDER_SENT", 5.0)
        if has_recent_reminder:
            return web.json_response({"status": "skipped", "reason": "recent_reminder"})

        if bot and target_user_id:
            await bot.send_message(
                chat_id=target_user_id,
                text="⏰ <b>Напоминание</b>: не забудьте записать приемы пищи за сегодня!",
                parse_mode="HTML",
            )
            await sheets.log_action("REMINDER_SENT", "Scheduler", "reminder_2130")
        return web.json_response({"status": "reminder_executed"})

    # 4. Cloud Scheduler: Дневной отчет
    async def job_daily_report(request: web.Request) -> web.Response:
        if scheduler_token:
            token = request.headers.get("X-Scheduler-Token") or request.query.get("token")
            if token != scheduler_token:
                return web.Response(status=403, text="Forbidden")

        if bot and target_user_id:
            settings = await sheets.get_settings()
            food_date = calculate_food_date(
                cutoff_hour=int(settings.get("DAY_CUTOFF_HOUR", 4)),
                tz_name=settings.get("TIMEZONE", "Asia/Almaty"),
            )
            records = await sheets.get_diary_records_for_date(food_date)
            summary = nutrition.format_daily_summary(records, settings)
            await bot.send_message(
                chat_id=target_user_id,
                text=f"🌙 <b>Итоги дня:</b>\n\n{summary}",
                parse_mode="HTML",
            )
        return web.json_response({"status": "daily_report_executed"})

    app.router.add_get("/health", healthcheck)
    app.router.add_post("/webhook", handle_webhook)
    app.router.add_post("/jobs/reminder", job_reminder)
    app.router.add_post("/jobs/daily-report", job_daily_report)

    return app


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is required in .env")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    app = create_app(bot=bot)

    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting server on port {port}...")
    web.run_app(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
