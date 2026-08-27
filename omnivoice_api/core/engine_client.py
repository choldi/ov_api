"""Cliente para interactuar con el motor OmniVoice."""

import asyncio
import logging
from typing import AsyncGenerator, AsyncIterator, Optional, Union

from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from omnivoice_api.core.omnivoice_engine import get_engine

logger = logging.getLogger(__name__)


class OmniVoiceClient:
    """Cliente para interactuar con el motor OmniVoice."""

    def __init__(self) -> None:
        self._engine = None
        self._connection_lock = asyncio.Lock()
        self._is_connected = False

    async def connect(self) -> None:
        """Conecta al motor OmniVoice."""
        async with self._connection_lock:
            if self._is_connected:
                return

            try:
                self._engine = await get_engine()
                await self._engine.initialize()
                self._is_connected = True
                logger.info("Conexión establecida con el motor OmniVoice")
            except EngineUnavailableError as e:
                logger.error("No se pudo conectar al motor OmniVoice: %s", e)
                raise

    async def disconnect(self) -> None:
        """Cierra la conexión con el motor."""
        async with self._connection_lock:
            if not self._is_connected:
                return

            try:
                await close_engine()
                self._is_connected = False
                logger.info("Conexión cerrada con el motor OmniVoice")
            except Exception as e:
                logger.error("Error al cerrar la conexión: %s", e)
                raise

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        language: str,
        speed: float = 1.0,
        emotion: Optional[str] = None,
        intensity: Optional[float] = None,
    ) -> bytes:
        """Sintetiza texto a audio usando una voz stock."""
        if not self._is_connected:
            await self.connect()

        try:
            return await self._engine.synthesize(
                text=text,
                voice_id=voice_id,
                language=language,
                speed=speed,
                emotion=emotion,
                intensity=intensity,
            )
        except VoiceNotFoundError as e:
            logger.error("Voz no encontrada: %s", e)
            raise
        except UnsupportedLanguageError as e:
            logger.error("Idioma no soportado: %s", e)
            raise
        except UnsupportedEmotionError as e:
            logger.error("Emoción no soportada: %s", e)
            raise

    async def synthesize_clone(
        self,
        text: str,
        reference_audio_path: str,
        language: str,
        emotion: Optional[str] = None,
        intensity: Optional[float] = None,
    ) -> bytes:
        """Sintetiza texto a audio usando una voz clonada."""
        if not self._is_connected:
            await self.connect()

        try:
            return await self._engine.synthesize_clone(
                text=text,
                reference_audio_path=reference_audio_path,
                language=language,
                emotion=emotion,
                intensity=intensity,
            )
        except NotImplementedError as e:
            logger.error("Clonado de voces no implementado: %s", e)
            raise

    async def list_stock_voices(
        self, language: Optional[str] = None
    ) -> list[dict]:
        """Lista todas las voces stock disponibles."""
        if not self._is_connected:
            await self.connect()

        try:
            return await self._engine.list_stock_voices(language=language)
        except Exception as e:
            logger.error("Error al listar voces: %s", e)
            raise

    async def list_emotions(self) -> list[str]:
        """Lista todas las emociones soportadas."""
        if not self._is_connected:
            await self.connect()

        try:
            return await self._engine.list_emotions()
        except Exception as e:
            logger.error("Error al listar emociones: %s", e)
            raise

    async def health_check(self) -> dict:
        """Verifica el estado del motor."""
        if not self._is_connected:
            await self.connect()

        try:
            return await self._engine.health_check()
        except Exception as e:
            logger.error("Error al verificar estado: %s", e)
            raise

    async def __aenter__(self) -> "OmniVoiceClient":
        """Soporte para async with."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[object],
    ) -> None:
        """Soporte para async with."""
        await self.disconnect()
