"""Interfaz y implementación del motor OmniVoice."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import struct
import sys
import threading
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


def _log_subprocess_context(operation: str, cmd: list[str]) -> None:
    """Log de diagnóstico del contexto donde se va a crear un subproceso."""
    try:
        loop = asyncio.get_running_loop()
        loop_info = (
            f"loop_id={id(loop)}, "
            f"loop_class={type(loop).__name__}, "
            f"is_proactor={isinstance(loop, asyncio.ProactorEventLoop)}, "
            f"is_selector={isinstance(loop, asyncio.SelectorEventLoop)}"
        )
    except RuntimeError:
        loop_info = "NO_RUNNING_LOOP"

    thread_info = f"thread_id={threading.get_ident()}, thread_name={threading.current_thread().name}"
    platform_info = f"platform={sys.platform}"

    logger.info(
        "Subprocess context for op=%s: %s | %s | %s | cmd=%s",
        operation, platform_info, thread_info, loop_info, cmd,
    )


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

    Envuelve la librería k2-fsa/OmniVoice real mediante invocación al CLI
    del venv externo configurado en settings. Si OMNIVOICE_USE_MOCK=True,
    genera tonos de prueba (útil para tests sin GPU/modelo).
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
        self._use_mock: bool = self._settings.OMNIVOICE_USE_MOCK

    async def initialize(self) -> None:
        """Inicializa el modelo (carga pesos, warm-up)."""
        if self._model is not None:
            logger.debug("Engine already initialized, _model is not None: %s", self._model is not None)
            return

        logger.info("Initializing OmniVoice engine...")
        self._settings = get_settings()
        self._use_mock = self._settings.OMNIVOICE_USE_MOCK
        logger.debug("Settings INSTALL_DIR: %s", self._settings.OMNIVOICE_INSTALL_DIR)
        logger.debug("Settings VENV_DIR: %s", self._settings.OMNIVOICE_VENV_DIR)
        logger.debug("Settings MODEL_PATH: %s", self._settings.OMNIVOICE_MODEL_PATH)
        logger.debug("Settings model_path property: %s", self._settings.model_path)
        logger.debug("Settings python_bin property: %s", self._settings.python_bin)
        logger.debug("Settings OMNIVOICE_USE_MOCK: %s", self._use_mock)

        self._device = self._settings.OMNIVOICE_DEVICE
        logger.info("Device set to: %s", self._device)

        if self._use_mock:
            logger.warning(
                "OMNIVOICE_USE_MOCK=True -> usando generación MOCK (tonos de prueba). "
                "El motor real NO será invocado."
            )
            self._model = object()  # Mock model object
            self._stock_voices = self._get_mock_stock_voices()
            await self.warmup()
            logger.info("Mock engine inicializado correctamente")
            return

        # --- Modo REAL: validar entorno antes de cargar ---
        logger.info("OMNIVOICE_USE_MOCK=False -> cargando motor REAL OmniVoice (k2-fsa)")
        try:
            await self._validate_real_engine_environment()
            self._model = object()  # Marcador de "modelo cargado" (la carga real ocurre en el subprocess)
            self._stock_voices = self._get_mock_stock_voices()  # TODO: cargar desde el motor real
            await self.warmup()
            logger.info(
                "Motor OmniVoice REAL inicializado correctamente. "
                "Las síntesis se delegarán al CLI en %s",
                self._settings.python_bin,
            )
        except EngineUnavailableError:
            # Ya viene con contexto suficiente, solo re-lanzamos
            raise
        except NotImplementedError as e:
            # Caso específico: el event loop activo no soporta subprocess_exec
            # (típico en Windows con SelectorEventLoop o cuando se invoca desde
            # un thread que no es el principal).
            logger.error(
                "NotImplementedError al inicializar motor real. Esto suele indicar "
                "que el event loop activo no soporta asyncio.subprocess. "
                "En Windows, asegúrate de usar WindowsProactorEventLoopPolicy. "
                "platform=%s, thread=%s",
                sys.platform,
                threading.current_thread().name,
            )
            raise EngineUnavailableError(
                f"Event loop no soporta subprocess_exec (NotImplementedError). "
                f"En Windows se requiere ProactorEventLoop. platform={sys.platform}, "
                f"thread={threading.current_thread().name}. "
                f"Error original: {e}"
            ) from e
        except Exception as e:
            logger.exception("Error inicializando motor OmniVoice real")
            raise EngineUnavailableError(f"Failed to initialize real OmniVoice engine: {e}") from e

    async def _validate_real_engine_environment(self) -> None:
        """Valida que el entorno para invocar el motor real está disponible."""
        python_bin = self._settings.python_bin
        if not python_bin.exists():
            raise EngineUnavailableError(
                f"Python del venv de OmniVoice no encontrado en: {python_bin}. "
                f"Verifica OMNIVOICE_VENV_DIR."
            )
        logger.info("Python del venv OmniVoice OK: %s", python_bin)

        model_path = self._settings.model_path
        if not model_path.exists():
            logger.warning(
                "Ruta de modelo no existe: %s. Se continuará pero la síntesis podría fallar.",
                model_path,
            )
        else:
            logger.info("Ruta de modelo OK: %s", model_path)

        # Verificar que el binario python es ejecutable
        cmd = [str(python_bin), "--version"]
        _log_subprocess_context(operation="validate_python_version", cmd=cmd)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self._settings.ENGINE_STARTUP_TIMEOUT_SEC,
            )
            version_line = (stdout or stderr).decode(errors="replace").strip()
            logger.info("Versión de Python del venv OmniVoice: %s", version_line)
            if proc.returncode != 0:
                raise EngineUnavailableError(
                    f"Python del venv OmniVoice no ejecutable (rc={proc.returncode}): {version_line}"
                )
        except NotImplementedError as e:
            logger.error(
                "NotImplementedError creando subproceso para validar python. "
                "cmd=%s. Esto indica que el event loop no soporta subprocess_exec.",
                cmd,
            )
            raise EngineUnavailableError(
                f"Event loop no soporta subprocess_exec al validar python del venv. "
                f"En Windows se requiere ProactorEventLoop. cmd={cmd}. Error: {e}"
            ) from e
        except asyncio.TimeoutError as e:
            raise EngineUnavailableError(
                f"Timeout verificando python del venv OmniVoice ({self._settings.ENGINE_STARTUP_TIMEOUT_SEC}s)"
            ) from e
        except FileNotFoundError as e:
            raise EngineUnavailableError(
                f"No se pudo ejecutar python del venv OmniVoice: {e}"
            ) from e

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
        if self._use_mock:
            logger.debug("Mock warmup: sleeping 10ms")
            await asyncio.sleep(0.01)
            return

        # En modo real, el warmup ocurre dentro del subprocess la primera vez.
        # Aquí solo verificamos que el CLI responde.
        logger.info("Warmup del motor REAL: verificando CLI OmniVoice...")
        try:
            python_bin = self._settings.python_bin
            cli_entry = self._settings.OMNIVOICE_CLI_ENTRY
            cmd = [str(python_bin), "-m", cli_entry, "--health"]
            _log_subprocess_context(operation="warmup_cli_health", cmd=cmd)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self._settings.ENGINE_STARTUP_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                logger.warning("Timeout en warmup --health del CLI OmniVoice (continuando)")
                return

            if proc.returncode == 0:
                logger.info(
                    "Warmup OK. CLI OmniVoice responde. stdout=%s",
                    stdout.decode(errors="replace").strip()[:200],
                )
            else:
                logger.warning(
                    "Warmup CLI OmniVoice rc=%d. stderr=%s",
                    proc.returncode,
                    stderr.decode(errors="replace").strip()[:500],
                )
        except NotImplementedError as e:
            logger.error(
                "NotImplementedError en warmup del CLI OmniVoice. "
                "El event loop activo no soporta subprocess_exec."
            )
            # No bloqueante: solo warning
            logger.warning("Warmup omitido por NotImplementedError: %s", e)
        except FileNotFoundError as e:
            logger.warning("No se pudo ejecutar CLI OmniVoice en warmup: %s", e)
        except Exception as e:
            logger.warning("Warmup del motor real falló (no bloqueante): %s", e)

    async def _invoke_omnivoice_cli(
        self,
        *,
        operation: str,
        payload: dict,
    ) -> bytes:
        """
        Invoca el CLI de OmniVoice en el venv externo y devuelve los WAV bytes.

        Contrato del CLI (esperado):
          python -m omnivoice_cli.__main__ --op <operation> [--in <path>] [--out <path>]
        - Lee un JSON con los parámetros desde --in <path> (o stdin).
        - Escribe el WAV resultante en --out <path> (o stdout en binario).

        Si el CLI no está disponible o falla, se lanza EngineUnavailableError.
        """
        python_bin = self._settings.python_bin
        cli_entry = self._settings.OMNIVOICE_CLI_ENTRY

        # Escribir payload a archivo temporal (más robusto que stdin para payloads grandes)
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as in_file:
            json.dump(payload, in_file, ensure_ascii=False)
            in_path = in_file.name

        out_path = tempfile.mktemp(suffix=".wav")

        cmd = [
            str(python_bin),
            "-m",
            cli_entry,
            "--op",
            operation,
            "--in",
            in_path,
            "--out",
            out_path,
        ]

        _log_subprocess_context(operation=operation, cmd=cmd)
        logger.info(
            "Invocando CLI OmniVoice REAL: op=%s, cmd=%s",
            operation,
            " ".join(cmd),
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=self._settings.ENGINE_REQUEST_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError as e:
                proc.kill()
                await proc.wait()
                raise EngineUnavailableError(
                    f"Timeout ({self._settings.ENGINE_REQUEST_TIMEOUT_SEC}s) invocando CLI OmniVoice "
                    f"para op={operation}"
                ) from e

            if proc.returncode != 0:
                err_msg = stderr.decode(errors="replace").strip()
                logger.error(
                    "CLI OmniVoice rc=%d para op=%s. stderr=%s",
                    proc.returncode,
                    operation,
                    err_msg[:1000],
                )
                raise EngineUnavailableError(
                    f"CLI OmniVoice falló (rc={proc.returncode}) para op={operation}: {err_msg[:500]}"
                )

            # Leer WAV de salida
            if not os.path.exists(out_path):
                raise EngineUnavailableError(
                    f"CLI OmniVoice no generó archivo de salida: {out_path}"
                )

            with open(out_path, "rb") as f:
                wav_bytes = f.read()

            logger.info(
                "CLI OmniVoice OK: op=%s, wav_bytes=%d, stdout_preview=%s",
                operation,
                len(wav_bytes),
                stdout.decode(errors="replace").strip()[:200],
            )
            return wav_bytes

        except NotImplementedError as e:
            logger.error(
                "NotImplementedError invocando CLI OmniVoice. "
                "El event loop activo no soporta subprocess_exec. "
                "op=%s, cmd=%s",
                operation, cmd,
            )
            raise EngineUnavailableError(
                f"Event loop no soporta subprocess_exec al invocar CLI OmniVoice. "
                f"En Windows se requiere ProactorEventLoop. op={operation}, cmd={cmd}. "
                f"Error: {e}"
            ) from e
        except FileNotFoundError as e:
            raise EngineUnavailableError(
                f"No se pudo ejecutar python del venv OmniVoice ({python_bin}): {e}"
            ) from e
        finally:
            # Limpieza de temporales
            for p in (in_path, out_path):
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except OSError:
                    pass

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
            "synthesize_stock called: text_len=%d, voice_id=%s, language=%s, speed=%.2f, emotion=%s, intensity=%s, use_mock=%s",
            len(text), voice_id, language, speed, emotion, intensity, self._use_mock
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

        logger.info(
            "Starting synthesis: voice_id=%s, language=%s, text='%s...', mode=%s",
            voice_id, language, text[:50], "MOCK" if self._use_mock else "REAL"
        )

        async with self._semaphore:
            if self._use_mock:
                # MOCK: Generar tono de prueba audible (440Hz)
                logger.warning(
                    "USING MOCK SYNTHESIS (OMNIVOICE_USE_MOCK=True) - "
                    "generating test tone (440Hz) instead of real OmniVoice output"
                )
                wav_bytes = self._generate_test_tone_wav(
                    duration_sec=max(0.5, len(text) * 0.08),
                    sample_rate=22050,
                    frequency=440.0,
                    amplitude=0.3,
                )
                logger.info(
                    "Mock synthesis completed: wav_bytes=%d, duration=%.2fs",
                    len(wav_bytes), len(text) * 0.08,
                )
                return wav_bytes

            # REAL: invocar CLI de OmniVoice
            payload = {
                "text": text,
                "voice_id": voice_id,
                "language": language,
                "speed": speed,
                "emotion": emotion,
                "intensity": intensity,
                "model_path": str(self._settings.model_path),
                "device": self._device,
            }
            wav_bytes = await self._invoke_omnivoice_cli(
                operation="synthesize_stock",
                payload=payload,
            )
            logger.info(
                "REAL synthesis completed via OmniVoice CLI: wav_bytes=%d",
                len(wav_bytes),
            )
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
            "synthesize_clone called: text_len=%d, ref_path=%s, language=%s, emotion=%s, intensity=%s, use_mock=%s",
            len(text), reference_audio_path, language, emotion, intensity, self._use_mock
        )

        # Validar idioma
        if language not in self._languages:
            logger.error("Unsupported language: %s, supported=%s", language, self._languages)
            raise UnsupportedLanguageError(language, self._languages)

        # Validar emoción
        if emotion and emotion not in self._emotions:
            logger.error("Unsupported emotion: %s, supported=%s", emotion, self._emotions)
            raise UnsupportedEmotionError(emotion, self._emotions)

        # Validar referencia (en modo real debe existir)
        if not self._use_mock and not os.path.exists(reference_audio_path):
            raise EngineUnavailableError(
                f"Reference audio no encontrado para clonado: {reference_audio_path}"
            )

        logger.info(
            "Starting clone synthesis: ref_path=%s, language=%s, text='%s...', mode=%s",
            reference_audio_path, language, text[:50], "MOCK" if self._use_mock else "REAL"
        )

        async with self._semaphore:
            if self._use_mock:
                # MOCK: Generar tono de prueba audible (880Hz)
                logger.warning(
                    "USING MOCK CLONE SYNTHESIS (OMNIVOICE_USE_MOCK=True) - "
                    "generating test tone (880Hz) instead of real OmniVoice output"
                )
                wav_bytes = self._generate_test_tone_wav(
                    duration_sec=max(0.5, len(text) * 0.08),
                    sample_rate=22050,
                    frequency=880.0,
                    amplitude=0.3,
                )
                logger.info("Mock clone synthesis completed: wav_bytes=%d", len(wav_bytes))
                return wav_bytes

            # REAL: invocar CLI de OmniVoice
            payload = {
                "text": text,
                "reference_audio_path": reference_audio_path,
                "language": language,
                "emotion": emotion,
                "intensity": intensity,
                "model_path": str(self._settings.model_path),
                "device": self._device,
            }
            wav_bytes = await self._invoke_omnivoice_cli(
                operation="synthesize_clone",
                payload=payload,
            )
            logger.info(
                "REAL clone synthesis completed via OmniVoice CLI: wav_bytes=%d",
                len(wav_bytes),
            )
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
            "mode": "MOCK" if self._use_mock else "REAL",
            "python_bin": str(self._settings.python_bin),
            "model_path": str(self._settings.model_path),
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
        amplitude: float = 0.3,
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
            sample = int(max_amplitude * value)
            samples.append(struct.pack('<h', sample))

        audio_data = b''.join(samples)

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
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
        _engine_instance = None
