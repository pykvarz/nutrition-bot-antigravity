import asyncio
import os
from typing import Optional


class GroqService:
    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("GROQ_API_KEY")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self._api_key)
        return self._client

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        filename: str = "voice.ogg",
        language: str = "ru",
    ) -> str:
        """
        Асинхронная транскрибация аудио через Groq Whisper-large-v3.
        """
        return await asyncio.to_thread(self._sync_transcribe, audio_bytes, filename, language)

    def _sync_transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "voice.ogg",
        language: str = "ru",
    ) -> str:
        client = self._get_client()
        transcription = client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3",
            language=language,
            response_format="text",
        )
        return str(transcription).strip()
