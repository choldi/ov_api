"""Configuración base de pytest y fixtures compartidas.

El engine OmniVoice vive en una instalación externa. En los tests unitarios
**no** se invoca nunca: se mockea a través de fixtures.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from omnivoice_api.core.engine_client import (
    AudioResult,
    EngineHealth,
    OmniVoiceEngineClient,
    StockVoice,
)
from omnivoice_api.main import app


# ---------------------------------------------------------------------------
# Cliente HTTP asíncrono
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client() -> AsyncIterator[AsyncClient]:
    """Cliente HTTP asíncrono para tests de integración."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Event loop (compatibilidad con versiones antiguas de pytest-asyncio)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop():
    """Fixture para el event loop de asyncio."""
    import asyncio

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Aislamiento de la instalación externa durante los tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_external_install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirige las rutas de la instalación externa a un tmp_path.

    Evita que los tests dependan de la instalación real en
    ``C:\\AI\\TTS\\OMNIVOICE\\...``.
    """
    fake_install = tmp_path / "OMNIVOICE"
    fake_venv = tmp_path / "omnivoice_env"
    fake_install.mkdir()
    fake_venv.mkdir()
    if fake_venv.name == "omnivoice_env" and "Scripts" not in fake_venv.parts:
        # Crear estructura mínima para que python_bin_from_venv() resuelva
        scripts = fake_venv / ("Scripts" if __import__("sys").platform == "win32" else "bin")
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / ("python.exe" if __import__("sys").platform == "win32" else "python")).touch()

    monkeypatch.setenv("OMNIVOICE_INSTALL_DIR", str(fake_install))
    monkeypatch.setenv("OMNIVOICE_VENV_DIR", str(fake_venv))

    # Invalidar el cache de settings para que se relean las env vars
    from omnivoice_api.settings import get_settings

    # Reiniciar el singleton para que se relean las env vars
    import omnivoice_api.settings
    omnivoice_api.settings._settings_instance = None

    # Debug: print the environment variables being set
    print(f"[DEBUG] Setting OMNIVOICE_INSTALL_DIR to: {str(fake_install)}")
    print(f"[DEBUG] Setting OMNIVOICE_VENV_DIR to: {str(fake_venv)}")

    yield

    # Reiniciar el singleton nuevamente para limpiar después del test
    import omnivoice_api.settings
    omnivoice_api.settings._settings_instance = None
    
    # Debug: print that we're cleaning up
    print(f"[DEBUG] Cleaning up after test")


# ---------------------------------------------------------------------------
# Mock del engine client
# ---------------------------------------------------------------------------


class FakeEngineClient(OmniVoiceEngineClient):
    """Implementación falsa del engine client para tests."""

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self._voices: list[StockVoice] = [
            StockVoice(voice_id="es-mx-male", language="es", gender="male", name="Carlos"),
            StockVoice(voice_id="es-mx-female", language="es", gender="female", name="Ana"),
            StockVoice(voice_id="en-us-male", language="en", gender="male", name="John"),
        ]
        self._emotions: list[str] = ["neutral", "happy", "sad", "angry", "surprised"]

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def health(self) -> EngineHealth:
        return EngineHealth(
            reachable=True,
            model_loaded=True,
            gpu_available=True,
            vram_free_mb=4096,
        )

    async def list_stock_voices(self, language: str | None = None) -> list[StockVoice]:
        if language is None:
            return list(self._voices)
        return [v for v in self._voices if v.language == language]

    async def list_emotions(self) -> list[str]:
        return list(self._emotions)

    async def synthesize_stock(
        self,
        *,
        text: str,
        voice_id: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> AudioResult:
        # WAV mínimo válido (header + 1 muestra de silencio)
        wav = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        return AudioResult(wav_bytes=wav, duration_sec=0.5, sample_rate=22050)

    async def synthesize_clone(
        self,
        *,
        text: str,
        reference_audio_path: Path,
        language: str,
        emotion: str | None = None,
        intensity: float | None = None,
    ) -> AudioResult:
        wav = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        return AudioResult(wav_bytes=wav, duration_sec=0.5, sample_rate=22050)

    async def stream_synthesize_stock(  # type: ignore[override]
        self,
        *,
        text: str,
        voice_id: str,
        language: str,
        speed: float = 1.0,
        emotion: str | None = None,
        intensity: float | None = None,
    ):
        result = await self.synthesize_stock(
            text=text,
            voice_id=voice_id,
            language=language,
            speed=speed,
            emotion=emotion,
            intensity=intensity,
        )
        for i in range(0, len(result.wav_bytes), 1024):
            yield result.wav_bytes[i : i + 1024]


@pytest.fixture
def fake_engine_client() -> FakeEngineClient:
    """Engine client falso listo para inyectar."""
    return FakeEngineClient()


@pytest.fixture
def mock_engine_client(monkeypatch: pytest.MonkeyPatch) -> FakeEngineClient:
    """Parchea el engine client global con el fake."""
    fake = FakeEngineClient()
    # Mockeamos el símbolo donde se importará en Sprint 1.
    # En Sprint 0 sólo dejamos el fixture disponible.
    monkeypatch.setattr(
        "omnivoice_api.core.engine_client.OmniVoiceEngineClient",
        lambda: fake,
    )
    return fake


# ---------------------------------------------------------------------------
# Fixtures de datos
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_text() -> str:
    """Texto de ejemplo para tests de TTS."""
    return "Hola, esto es una prueba de síntesis de voz."


@pytest.fixture
def sample_voice_id() -> str:
    """ID de voz de ejemplo para tests."""
    return "es-mx-male"


@pytest.fixture
def sample_audio_bytes() -> bytes:
    """Bytes de un WAV mínimo válido para tests de clonado."""
    return (
        b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
        b"\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00"
        b"\x02\x00\x10\x00data\x00\x00\x00\x00"
    )

