import io
import os
import logging
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command

from bot.models.intents import ParsedIntent, IntentType
from bot.services.gemini_service import GeminiService
from bot.services.groq_service import GroqService
from bot.handlers.domain import DomainHandler

logger = logging.getLogger(__name__)


def create_bot_router(
    domain_handler: DomainHandler,
    gemini_service: GeminiService,
    groq_service: GroqService,
    allowed_user_id: Optional[int] = None,
) -> Router:
    router = Router()
    target_user_id = allowed_user_id or int(os.getenv("ALLOWED_TELEGRAM_USER_ID", "0"))

    def check_user(message: Message) -> bool:
        if target_user_id and message.from_user and message.from_user.id != target_user_id:
            logger.warning(f"Unauthorized access attempt from user_id={message.from_user.id}")
            return False
        return True

    @router.message(Command("start"))
    async def cmd_start(message: Message):
        if not check_user(message):
            await message.answer("⛔ Доступ ограничен.")
            return
        await message.answer(
            "👋 <b>Привет! Я твой персональный бот-нутрициолог.</b>\n\n"
            "Я помогу вести дневник питания, считать калории и КБЖУ.\n\n"
            "<b>Что я умею:</b>\n"
            "• Принимать записи голосом, текстом или фото еды\n"
            "• Считать суточный баланс калорий и макронутриентов\n"
            "• Учитывать физическую активность\n"
            "• Отменять ошибочные записи (/undo)\n"
            "• Показывать сводку за сегодня (/today)\n\n"
            "<i>Просто напиши, отправь голосовое или сфотографируй то, что съел!</i>",
            parse_mode="HTML",
        )

    @router.message(Command("help"))
    async def cmd_help(message: Message):
        if not check_user(message):
            return
        await message.answer(
            "📖 <b>Команды и возможности:</b>\n\n"
            "/today — сводка съеденного и активности за сегодня\n"
            "/undo — отменить последнюю запись\n"
            "/advice — персональный совет по питанию на вечер\n"
            "/settings — текущие цели калорий и КБЖУ\n\n"
            "<b>Примеры сообщений:</b>\n"
            "• «Съел 250г творога и банан»\n"
            "• «Повтори обед» или «Съел половину прошлого ужина»\n"
            "• «Бег 40 минут»\n"
            "• Отправка фото тарелки с едой\n"
            "• Голосовое сообщение",
            parse_mode="HTML",
        )

    @router.message(Command("today"))
    async def cmd_today(message: Message):
        if not check_user(message):
            return
        intent = ParsedIntent(intent=IntentType.TODAY, raw_text="/today")
        reply = await domain_handler.process_intent(
            intent=intent,
            update_id=message.message_id,
            message_id=message.message_id,
        )
        await message.answer(reply, parse_mode="HTML")

    @router.message(Command("undo"))
    async def cmd_undo(message: Message):
        if not check_user(message):
            return
        intent = ParsedIntent(intent=IntentType.UNDO, raw_text="/undo")
        reply = await domain_handler.process_intent(
            intent=intent,
            update_id=message.message_id,
            message_id=message.message_id,
        )
        await message.answer(reply, parse_mode="HTML")

    @router.message(Command("advice"))
    async def cmd_advice(message: Message):
        if not check_user(message):
            return
        intent = ParsedIntent(intent=IntentType.ADVICE, raw_text="/advice")
        reply = await domain_handler.process_intent(
            intent=intent,
            update_id=message.message_id,
            message_id=message.message_id,
        )
        await message.answer(reply, parse_mode="HTML")

    @router.message(Command("settings"))
    async def cmd_settings(message: Message):
        if not check_user(message):
            return
        intent = ParsedIntent(intent=IntentType.SETTINGS, raw_text="/settings")
        reply = await domain_handler.process_intent(
            intent=intent,
            update_id=message.message_id,
            message_id=message.message_id,
        )
        await message.answer(reply, parse_mode="HTML")

    @router.message(F.voice)
    async def handle_voice(message: Message, bot: Bot):
        if not check_user(message):
            return
        voice = message.voice
        if not voice:
            return

        file = await bot.get_file(voice.file_id)
        file_path = file.file_path
        if not file_path:
            await message.answer("Не удалось загрузить аудиофайл.")
            return

        file_stream = io.BytesIO()
        await bot.download_file(file_path, destination=file_stream)
        audio_bytes = file_stream.getvalue()

        # Transcribe via Groq Whisper
        transcribed_text = await groq_service.transcribe_audio(audio_bytes)
        if not transcribed_text:
            await message.answer("Не удалось разобрать голосовое сообщение.")
            return

        await message.answer(f"🗣 <i>«{transcribed_text}»</i>", parse_mode="HTML")

        # Parse text via Gemini
        intent = await gemini_service.parse_text(transcribed_text)
        reply = await domain_handler.process_intent(
            intent=intent,
            update_id=message.message_id,
            message_id=message.message_id,
            source="voice",
        )
        await message.answer(reply, parse_mode="HTML")

    @router.message(F.photo)
    async def handle_photo(message: Message, bot: Bot):
        if not check_user(message):
            return
        photo = message.photo[-1]  # Highest resolution
        file = await bot.get_file(photo.file_id)
        if not file.file_path:
            await message.answer("Не удалось загрузить фотографию.")
            return

        file_stream = io.BytesIO()
        await bot.download_file(file.file_path, destination=file_stream)
        image_bytes = file_stream.getvalue()

        intent = await gemini_service.parse_image(
            image_bytes=image_bytes,
            caption=message.caption,
        )
        reply = await domain_handler.process_intent(
            intent=intent,
            update_id=message.message_id,
            message_id=message.message_id,
            source="photo",
        )
        await message.answer(reply, parse_mode="HTML")

    @router.message(F.text)
    async def handle_text(message: Message):
        if not check_user(message):
            return
        text = message.text or ""
        intent = await gemini_service.parse_text(text)
        reply = await domain_handler.process_intent(
            intent=intent,
            update_id=message.message_id,
            message_id=message.message_id,
            source="text",
        )
        await message.answer(reply, parse_mode="HTML")

    return router
