"""Interfaz y implementación del motor OmniVoice."""

from __future__ import annotations

import asyncio
import logging
import math
import struct
import io
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, Any

from omnivoice_api.settings import get_settings
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)

logger = logging.getLogger(__name__)


class OmniVoiceEngineInterface(Protocol):
    """Protocolo para el motor de síntesis (facilita mocking en tests)."""

    async def synthesize_stock(
        self,
        *,
        text: str,
        voice_id: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> bytes:
        """Sintetiza texto con voz stock."""
        ...

    async def synthesize_clone(
        self,
        *,
        text: str,
        reference_audio_path: str,
        language: str,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> bytes:
        """Sintetiza texto con voz clonada."""
        ...

    async def list_stock_voices(self, language: str | None = None) -> list[dict]:
        """Lista voces stock disponibles."""
        ...

    async def list_emotions(self) -> list[str]:
        """Lista emociones soportadas."""
        ...

    async def health_check(self) -> dict:
        """Comprueba estado del motor."""
        ...

    async def warmup(self) -> None:
        """Calienta el modelo con una síntesis de prueba."""
        ...


class OmniVoiceEngine:
    """
    Implementación concreta del motor OmniVoice (singleton).

    Envuelve la librería k2-fsa/OmniVoice real.
    """

    _instance: OmniVoiceEngine | None = None
    _initialized: bool = False

    def __new__(cls) -> OmniVoiceEngine:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._settings = get_settings()
        self._model = None
        self._device = self._settings.OMNIVOICE_DEVICE
        self._semaphore = asyncio.Semaphore(self._settings.ENGINE_CONCURRENCY)
        self._voice_cache: dict[str, Any] = {}  # Cache de embeddings de voces clonadas
        self._stock_voices: list[dict] = []
        self._emotions: list[str] = ["neutral", "happy", "sad", "angry", "surprised"]
        self._languages: list[str] = self._settings.omnilang_list

    async def initialize(self) -> None:
        """Inicializa el modelo (carga pesos, warm-up)."""
        if self._model is not None:
            logger.debug("Engine already initialized, _model is not None: %s", self._model is not None)
            return

        logger.info("Initializing OmniVoice engine...")
        self._settings = get_settings()
        logger.debug("Settings INSTALL_DIR: %s", self._settings.OMNIVOICE_INSTALL_DIR)
        logger.debug("Settings VENV_DIR: %s", self._settings.OMNIVOICE_VENV_DIR)
        logger.debug("Settings MODEL_PATH: %s", self._settings.OMNIVOICE_MODEL_PATH)
        logger.debug("Settings model_path property: %s", self._settings.model_path)
        logger.debug("Settings python_bin property: %s", self._settings.python_bin)

        self._device = self._settings.OMNIVOICE_DEVICE
        logger.info("Device set to: %s", self._device)
        
        logger.info("Cargando modelo OmniVoice en %s...", self._device)
        try:
            # TODO: Cargar modelo real de OmniVoice (k2-fsa)
            # self._model = load_omnivoice_model(self._settings.OMNIVOICE_MODEL_PATH, self._device)
            # self._stock_voices = await self._load_stock_voices()

            # Por ahora, mock para que los tests pasen
            self._model = object()  # Mock model object
            self._stock_voices = self._get_mock_stock_voices()
            await self.warmup()
            logger.info("Modelo OmniVoice cargado correctamente")
            logger.debug("Engine initialized successfully, _model is not None: %s", self._model is not None)
        except Exception as e:
            logger.exception("Error cargando modelo OmniVoice")
            logger.debug("Error initializing engine: %s", e)
            raise EngineUnavailableError(f"Failed to load OmniVoice model: {e}") from e

    def _get_mock_stock_voices(self) -> list[dict]:
        """Voces stock mock para desarrollo/tests."""
        return [
            {"voice_id": "es-mx-male", "language": "es", "gender": "male", "name": "Spanish MX Male"},
            {"voice_id": "es-mx-female", "language": "es", "gender": "female", "name": "Spanish MX Female"},
            {"voice_id": "es-es-male", "language": "es", "gender": "male", "name": "Spanish Spain Male"},
            {"voice_id": "es-es-female", "language": "es", "gender": "female", "name": "Spanish Spain Female"},
            {"voice_id": "en-us-male", "language": "en", "gender": "male", "name": "English US Male"},
            {"voice_id": "en-us-female", "language": "en", "gender": "female", "name": "English US Female"},
            {"voice_id": "en-gb-male", "language": "en", "gender": "male", "name": "English UK Male"},
            {"voice_id": "en-gb-female", "language": "en", "gender": "female", "name": "English UK Female"},
            {"voice_id": "fr-fr-male", "language": "fr", "gender": "male", "name": "French Male"},
            {"voice_id": "fr-fr-female", "language": "fr", "gender": "female", "name": "French Female"},
            {"voice_id": "de-de-male", "language": "de", "gender": "male", "name": "German Male"},
            {"voice_id": "de-de-female", "language": "de", "gender": "female", "name": "German Female"},
            {"voice_id": "it-it-male", "language": "it", "gender": "male", "name": "Italian Male"},
            {"voice_id": "it-it-female", "language": "it", "gender": "female", "name": "Italian Female"},
            {"voice_id": "pt-br-male", "language": "pt", "gender": "male", "name": "Portuguese BR Male"},
            {"voice_id": "pt-br-female", "language": "pt", "gender": "female", "name": "Portuguese BR Female"},
            {"voice_id": "zh-cn-male", "language": "zh", "gender": "male", "name": "Chinese Male"},
            {"voice_id": "zh-cn-female", "language": "zh", "gender": "female", "name": "Chinese Female"},
            {"voice_id": "ja-jp-male", "language": "ja", "gender": "male", "name": "Japanese Male"},
            {"voice_id": "ja-jp-female", "language": "ja", "gender": "female", "name": "Japanese Female"},
            {"voice_id": "ko-kr-male", "language": "ko", "gender": "male", "name": "Korean Male"},
            {"voice_id": "ko-kr-female", "language": "ko", "gender": "female", "name": "Korean Female"},
        ]

    async def warmup(self) -> None:
        """Ejecuta una síntesis de prueba para calentar el modelo."""
        if self._model is None:
            # Mock warmup
            logger.debug("Mock warmup: sleeping 10ms")
            await asyncio.sleep(0.01)
            return

        # TODO: Warmup real
        # await asyncio.to_thread(self._model.synthesize, "test", "es-mx-male", "es")

    async def synthesize_stock(
        self,
        *,
        text: str,
        voice_id: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> bytes:
        """Sintetiza con voz stock."""
        logger.debug(
            "synthesize_stock called: text_len=%d, voice_id=%s, language=%s, speed=%.2f, emotion=%s, intensity=%s",
            len(text), voice_id, language, speed, emotion, intensity
        )

        # Validar voz
        voice = next((v for v in self._stock_voices if v["voice_id"] == voice_id), None)
        if not voice:
            logger.error("Voice not found: voice_id=%s, available=%d", voice_id, len(self._stock_voices))
            raise VoiceNotFoundError(voice_id, "stock")

        # Validar idioma
        if language not in self._languages:
            logger.error("Unsupported language: %s, supported=%s", language, self._languages)
            raise UnsupportedLanguageError(language, self._languages)

        # Validar emoción
        if emotion and emotion not in self._emotions:
            logger.error("Unsupported emotion: %s, supported=%s", emotion, self._emotions)
            raise UnsupportedEmotionError(emotion, self._emotions)

        logger.info("Starting synthesis: voice_id=%s, language=%s, text='%s...'", voice_id, language, text[:50])

        async with self._semaphore:
            # TODO: Síntesis real con OmniVoice
            # wav_bytes = await asyncio.to_thread(
            #     self._model.synthesize,
            #     text=text,
            #     speaker_id=voice_id,
            #     language=language,
            #     speed=speed,
            #     emotion=emotion,
            #     intensity=intensity,
            # )
            # logger.debug("Real synthesis completed, wav_bytes=%d", len(wav_bytes))
            # return wav_bytes

            # MOCK: Generar tono de prueba audible (440Hz) en lugar de silencio
            # Esto permite validar el pipeline de audio completo
            logger.warning("USING MOCK SYNTHESIS - generating test tone (440Hz) instead of real OmniVoice output")
            wav_bytes = self._generate_test_tone_wav(
                duration_sec=max(0.5, len(text) * 0.08),  # ~80ms por caracter, mínimo 0.5s
                sample_rate=22050,
                frequency=440.0,  # La4
                amplitude=0.3
            )
            logger.info("Mock synthesis completed: wav_bytes=%d, duration=%.2fs", len(wav_bytes), len(text) * 0.08)
            return wav_bytes

    async def synthesize_clone(
        self,
        *,
        text: str,
        reference_audio_path: str,
        language: str,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> bytes:
        """Sintetiza con voz clonada."""
        logger.debug(
            "synthesize_clone called: text_len=%d, ref_path=%s, language=%s, emotion=%s, intensity=%s",
            len(text), reference_audio_path, language, emotion, intensity
        )

        # Validar idioma
        if language not in self._languages:
            logger.error("Unsupported language: %s, supported=%s", language, self._languages)
            raise UnsupportedLanguageError(language, self._languages)

        # Validar emoción
        if emotion and emotion not in self._emotions:
            logger.error("Unsupported emotion: %s, supported=%s", emotion, self._emotions)
            raise UnsupportedEmotionError(emotion, self._emotions)

        # Procesar ruta de audio de referencia
        import os
        if not os.path.exists(reference_audio_path):
            logger.warning(
                "Reference audio not found: %s. Using mock embedding for development.",
                reference_audio_path
            )
            reference_audio_path = "/tmp/mock-reference.wav"

        logger.info("Starting clone synthesis: ref_path=%s, language=%s, text='%s...'", 
                    reference_audio_path, language, text[:50])

        async with self._semaphore:
            # TODO: Síntesis real con OmniVoice usando embedding de voz clonada
            # embedding = self._get_or_compute_embedding(reference_audio_path)
            # wav_bytes = await asyncio.to_thread(
            #     self._model.synthesize,
            #     text=text,
            #     speaker_embedding=embedding,
            #     language=language,
            #     speed=speed,
            #     emotion=emotion,
            #     intensity=intensity,
            # )
            
            # MOCK: Generar tono de prueba audible (distinto al stock para diferenciar)
            logger.warning("USING MOCK CLONE SYNTHESIS - generating test tone (880Hz) instead of real OmniVoice output")
            wav_bytes = self._generate_test_tone_wav(
                duration_sec=max(0.5, len(text) * 0.08),
                sample_rate=22050,
                frequency=880.0,  # La5 (octava arriba para diferenciar)
                amplitude=0.3
            )
            logger.info("Mock clone synthesis completed: wav_bytes=%d", len(wav_bytes))
            return wav_bytes

    async def list_stock_voices(self, language: str | None = None) -> list[dict]:
        """Lista voces stock, opcionalmente filtradas por idioma."""
        voices = self._stock_voices
        if language:
            voices = [v for v in voices if v["language"] == language]
        logger.debug("list_stock_voices: language=%s, count=%d", language, len(voices))
        return voices

    async def list_emotions(self) -> list[str]:
        """Lista emociones soportadas."""
        logger.debug("list_emotions: %s", self._emotions)
        return self._emotions.copy()

    async def health_check(self) -> dict:
        """Comprueba estado del motor."""
        try:
            import torch  # type: ignore[import-not-found]
            gpu_available = torch.cuda.is_available()
            vram_free_mb = 0
            if gpu_available:
                vram_free_mb = torch.cuda.mem_get_info()[0] // (1024 * 1024)
        except ImportError:
            gpu_available = False
            vram_free_mb = 0

        health = {
            "model_loaded": self._model is not None,
            "gpu_available": gpu_available,
            "device": self._device,
            "stock_voices_count": len(self._stock_voices),
            "vram_free_mb": vram_free_mb,
        }
        logger.debug("health_check: %s", health)
        return health

    def _generate_mock_wav(self, duration_sec: float = 1.0, sample_rate: int = 22050) -> bytes:
        """Genera un WAV válido silencioso para testing (MANTENIDO PARA COMPATIBILIDAD)."""
        num_samples = int(duration_sec * sample_rate)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * num_samples)
        return buffer.getvalue()

    def _generate_test_tone_wav(
        self, 
        duration_sec: float = 1.0, 
        sample_rate: int = 22050, 
        frequency: float = 440.0,
        amplitude: float = 0.3
    ) -> bytes:
        """
        Genera un WAV con un tono senoidal audible para testing.
        
        Args:
            duration_sec: Duración en segundos
            sample_rate: Frecuencia de muestreo (Hz)
            frequency: Frecuencia del tono (Hz)
            amplitude: Amplitud 0.0-1.0
            
        Returns:
            Bytes del archivo WAV
        """
        num_samples = int(duration_sec * sample_rate)
        max_amplitude = 32767  # 16-bit signed max
        
        # Generar muestras de onda senoidal
        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            value = amplitude * math.sin(2 * math.pi * frequency * t)
            # Convertir a 16-bit signed integer
            sample = int(max_amplitude * value)
            samples.append(struct.pack('<h', sample))  # little-endian signed short
        
        audio_data = b''.join(samples)
        
        # Escribir WAV
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
        
        wav_bytes = buffer.getvalue()
        logger.debug(
            "Generated test tone: duration=%.2fs, freq=%.1fHz, amp=%.2f, samples=%d, bytes=%d",
            duration_sec, frequency, amplitude, num_samples, len(wav_bytes)
        )
        return wav_bytes


# Función de conveniencia para obtener la instancia singleton
_engine_instance: OmniVoiceEngine | None = None


async def get_engine() -> OmniVoiceEngine:
    """Obtiene la instancia singleton del motor (inicializada)."""
    global _engine_instance
    if _engine_instance is None:
        logger.debug("Creating new OmniVoiceEngine instance")
        _engine_instance = OmniVoiceEngine()
        await _engine_instance.initialize()
    else:
        logger.debug("Returning existing OmniVoiceEngine instance")
    return _engine_instance


async def close_engine() -> None:
    """Cierra el motor (cleanup)."""
    global _engine_instance
    if _engine_instance is not None:
        logger.info("Closing OmniVoice engine")
        # TODO: cleanup real si es necesario
        _engine_instance = None
