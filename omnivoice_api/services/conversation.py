"""Servicio de conversaciones multi-voz."""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass

from omnivoice_api.core.engine_client import AudioResult, OmniVoiceEngineClient
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    VoiceNotFoundError,
)


@dataclass
class ConversationTurn:
    """Un turno de una conversación."""
    voice_id: str
    text: str


class ConversationService:
    """Servicio para generar audio de conversaciones multi-voz."""

    def __init__(self, engine_client: OmniVoiceEngineClient | None = None) -> None:
        self._engine_client = engine_client

    async def _get_engine_client(self) -> OmniVoiceEngineClient:
        if self._engine_client is None:
            self._engine_client = OmniVoiceEngineClient()
            await self._engine_client.start()
        return self._engine_client

    async def generate(
        self,
        *,
        turns: list[ConversationTurn],
        pause_ms: int = 300,
    ) -> AudioResult:
        """Genera audio concatenando múltiples turnos con silencios entre ellos.

        Args:
            turns: Lista de turnos (voice_id + text). Mínimo 2.
            pause_ms: Milisilundos de silencio entre turnos (default: 300).

        Returns:
            AudioResult con el WAV concatenado.

        Raises:
            ValueError: Si hay menos de 2 turnos o text vacío.
            VoiceNotFoundError: Si alguna voz no existe.
        """
        if len(turns) < 2:
            raise ValueError("Se requieren al menos 2 turnos para una conversación")

        for i, turn in enumerate(turns):
            if not turn.text or not turn.text.strip():
                raise ValueError(f"El turno {i+1} tiene texto vacío")

        engine = await self._get_engine_client()

        # Validar que todas las voces existen
        stock_voices = await engine.list_stock_voices()
        valid_ids = {v.voice_id for v in stock_voices}
        for turn in turns:
            if turn.voice_id not in valid_ids:
                raise VoiceNotFoundError(turn.voice_id, "stock")

        # Sintetizar cada turno
        audio_segments: list[bytes] = []
        sample_rate = 22050  # default mock rate

        for turn in turns:
            result = await engine.synthesize_stock(
                text=turn.text,
                voice_id=turn.voice_id,
            )
            audio_segments.append(result.wav_bytes)
            sample_rate = result.sample_rate

        # Concatenar con silencios
        concatenated = self._concatenate_wav(audio_segments, sample_rate, pause_ms)

        return AudioResult(
            wav_bytes=concatenated,
            duration_sec=0.0,  # Se calcula del WAV resultante
            sample_rate=sample_rate,
        )

    def _concatenate_wav(
        self,
        wav_segments: list[bytes],
        sample_rate: int,
        pause_ms: int,
    ) -> bytes:
        """Concatena múltiples WAVs con silencios entre ellos."""
        import struct

        all_frames = bytearray()

        for i, wav_bytes in enumerate(wav_segments):
            # Extraer frames del WAV
            frames = self._extract_wav_frames(wav_bytes)
            all_frames.extend(frames)

            # Agregar silencio entre turnos (no después del último)
            if i < len(wav_segments) - 1 and pause_ms > 0:
                silence_samples = int(sample_rate * pause_ms / 1000)
                silence_bytes = struct.pack(f"<{silence_samples}h", *([0] * silence_samples))
                all_frames.extend(silence_bytes)

        # Construir WAV resultante
        return self._build_wav(bytes(all_frames), sample_rate)

    def _extract_wav_frames(self, wav_bytes: bytes) -> bytes:
        """Extrae los frames de audio de un WAV (sin cabecera)."""
        # Buscar el chunk 'data'
        data_pos = wav_bytes.find(b"data")
        if data_pos == -1:
            return wav_bytes  # Fallback: devolver todo

        # Los 4 bytes después de "data" son el tamaño del chunk
        data_size = int.from_bytes(wav_bytes[data_pos + 4: data_pos + 8], byteorder="little")
        return wav_bytes[data_pos + 8: data_pos + 8 + data_size]

    def _build_wav(self, frames: bytes, sample_rate: int) -> bytes:
        """Construye un WAV válido a partir de frames raw."""
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(frames)
        return buffer.getvalue()

    async def close(self) -> None:
        if self._engine_client is not None:
            await self._engine_client.stop()
            self._engine_client = None
