"""Interfaz y implementación del motor OmniVoice."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import struct
import subprocess
import sys
import threading
import io
import wave
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


def _loop_supports_subprocess() -> bool:
    """Detecta si el event loop activo soporta asyncio.subprocess."""
    try:
        loop = asyncio.get_running_loop()
        return isinstance(loop, asyncio.ProactorEventLoop) or sys.platform != "win32"
    except RuntimeError:
        return True


async def _run_subprocess_async(
    cmd: list[str],
    timeout: float | None = None,
) -> tuple[int, bytes, bytes]:
    """
    Ejecuta un comando subprocess de forma asíncrona.
    """
    logger.info("Subprocess: cmd=%s", " ".join(cmd))
    
    if _loop_supports_subprocess():
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
            return proc.returncode, stdout or b"", stderr or b""
        except NotImplementedError:
            logger.warning("asyncio.subprocess no soportado, usando fallback síncrono")

    # Fallback síncrono
    result = await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


class OmniVoiceEngineInterface(Protocol):
    """Protocolo para el motor de síntesis."""

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
        ...

    async def list_stock_voices(self, language: str | None = None) -> list[dict]:
        ...

    async def list_emotions(self) -> list[str]:
        ...

    async def health_check(self) -> dict:
        ...

    async def warmup(self) -> None:
        ...


class OmniVoiceEngine:
    """
    Implementación del motor OmniVoice (singleton).
    
    Si OMNIVOICE_USE_MOCK=True, genera tonos de prueba.
    Si OMNIVOICE_USE_MOCK=False, invoca el CLI del venv externo.
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
        self._model: Any = None
        self._device = self._settings.OMNIVOICE_DEVICE
        self._semaphore = asyncio.Semaphore(self._settings.ENGINE_CONCURRENCY)
        self._stock_voices: list[dict] = []
        self._emotions: list[str] = ["neutral", "happy", "sad", "angry", "surprised"]
        self._languages: list[str] = self._settings.omnilang_list
        self._use_mock: bool = self._settings.OMNIVOICE_USE_MOCK
        self._cli_path: Path | None = None  # Ruta directa al script CLI

    async def initialize(self) -> None:
        """Inicializa el modelo."""
        if self._model is not None:
            return

        logger.info("Initializing OmniVoice engine...")
        self._settings = get_settings()
        self._use_mock = self._settings.OMNIVOICE_USE_MOCK
        logger.info("OMNIVOICE_USE_MOCK=%s", self._use_mock)

        self._device = self._settings.OMNIVOICE_DEVICE

        if self._use_mock:
            logger.warning("MODO MOCK: generando tonos de prueba")
            self._model = object()
            self._stock_voices = self._get_mock_stock_voices()
            await self.warmup()
            logger.info("Mock engine inicializado")
            return

        # Modo REAL
        logger.info("Modo REAL: buscando CLI de OmniVoice...")
        
        # Intentar encontrar la ruta directa al CLI
        self._cli_path = await self._find_omnivoice_cli()
        
        if self._cli_path is None:
            logger.warning("No se pudo encontrar CLI de OmniVoice, intentando invocar como módulo...")
        
        self._model = object()
        self._stock_voices = self._get_mock_stock_voices()
        await self.warmup()
        logger.info("Engine OmniVoice REAL inicializado")

    async def _find_omnivoice_cli(self) -> Path | None:
        """
        Busca la ruta directa al script CLI de OmniVoice.
        
        Returns:
            Path al script CLI o None si no se encuentra.
        """
        venv_dir = self._settings.OMNIVOICE_VENV_DIR
        python_bin = self._settings.python_bin
        
        # Posibles ubicaciones del CLI en Windows
        possible_paths = [
            venv_dir / "Scripts" / "omnivoice.exe",
            venv_dir / "Scripts" / "omnivoice-cli.exe",
            venv_dir / "Scripts" / "omnivoice_cli.exe",
            venv_dir / "Scripts" / "omni_voice.exe",
            venv_dir / "Scripts" / "omnivoice-script.py",
            venv_dir / "Scripts" / "omnivoice_cli-script.py",
        ]
        
        # En Unix
        if sys.platform != "win32":
            possible_paths = [
                venv_dir / "bin" / "omnivoice",
                venv_dir / "bin" / "omnivoice-cli",
            ]
        
        for cli_path in possible_paths:
            if cli_path.exists():
                logger.info("CLI de OmniVoice encontrado en: %s", cli_path)
                return cli_path
        
        # Verificar si hay scripts de consola en site-packages
        site_packages = venv_dir / "Lib" / "site-packages"
        if not site_packages.exists():
            site_packages = venv_dir / "lib" / "python3.11" / "site-packages"
        
        if site_packages.exists():
            # Buscar scripts de consola
            console_scripts = site_packages / "console_scripts"
            if console_scripts.exists():
                for f in console_scripts.iterdir():
                    if "omnivoice" in f.name.lower():
                        logger.info("CLI encontrado en console_scripts: %s", f)
                        return f
        
        return None

    def _get_cli_commands(self, *args: str) -> list[list[str]]:
        """
        Obtiene comandos posibles para invocar el CLI.
        
        Returns:
            Lista de comandos a intentar.
        """
        python_bin = self._settings.python_bin
        commands: list[list[str]] = []
        
        # Si tenemos la ruta directa al CLI, usarlo primero
        if self._cli_path is not None:
            commands.append([str(self._cli_path)] + list(args))
            # En Windows, los scripts .py necesitan python.exe
            if self._cli_path.suffix == ".py":
                commands.insert(0, [str(python_bin), str(self._cli_path)] + list(args))
        
        # Intentar con python -m
        cli_module = self._settings.OMNIVOICE_CLI_MODULE
        commands.append([str(python_bin), "-m", cli_module] + list(args))
        
        # Intentar con el módulo base
        if "." in cli_module:
            base_module = cli_module.split(".")[0]
            commands.append([str(python_bin), "-m", base_module] + list(args))
        
        return commands

    async def warmup(self) -> None:
        """Verifica que el CLI responde."""
        if self._use_mock:
            await asyncio.sleep(0.01)
            return

        logger.info("Warmup: verificando CLI OmniVoice...")
        
        # Intentar con --health o --help
        test_args = ["--help"]
        
        for cmd in self._get_cli_commands(*test_args):
            try:
                returncode, stdout, stderr = await _run_subprocess_async(
                    cmd,
                    timeout=10,
                )
                output = (stdout + stderr).decode(errors="replace")
                
                if returncode in (0, 1):  # --help típicamente devuelve 1
                    logger.info("Warmup OK con cmd=%s", " ".join(cmd[:3]))
                    return
                else:
                    logger.debug("Warmup falló con rc=%d: %s", returncode, output[:200])
            except Exception as e:
                logger.debug("Warmup exception con cmd=%s: %s", cmd[:3], e)
        
        logger.warning("Warmup no pudo verificar el CLI")

    async def _invoke_cli(
        self,
        *,
        operation: str,
        payload: dict,
    ) -> bytes:
        """Invoca el CLI de OmniVoice y devuelve los WAV bytes."""
        import tempfile
        
        # Escribir payload a archivo temporal
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as in_file:
            json.dump(payload, in_file, ensure_ascii=False)
            in_path = in_file.name

        out_path = tempfile.mktemp(suffix=".wav")

        cli_args = ["--op", operation, "--in", in_path, "--out", out_path]
        commands = self._get_cli_commands(*cli_args)
        
        cwd = str(self._settings.OMNIVOICE_VENV_DIR)
        env = os.environ.copy()
        venv_dir = self._settings.OMNIVOICE_VENV_DIR
        if venv_dir:
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(venv_dir) + (os.pathsep + existing if existing else "")

        last_error: Exception | None = None
        
        for cmd in commands:
            logger.info("Invocando CLI: %s", " ".join(cmd[:5]))
            
            try:
                returncode, stdout, stderr = await _run_subprocess_async(
                    cmd,
                    timeout=self._settings.ENGINE_REQUEST_TIMEOUT_SEC,
                )

                if returncode != 0:
                    err_msg = stderr.decode(errors="replace").strip()
                    # Si es error de "package cannot be executed", probar siguiente método
                    if "is a package" in err_msg or "No module named" in err_msg:
                        logger.debug("Método no aplicable: %s", err_msg[:100])
                        last_error = EngineUnavailableError(err_msg)
                        continue
                    
                    raise EngineUnavailableError(
                        f"CLI falló (rc={returncode}): {err_msg[:500]}"
                    )

                if not os.path.exists(out_path):
                    raise EngineUnavailableError(f"CLI no generó archivo: {out_path}")

                wav_bytes = await asyncio.to_thread(
                    lambda: open(out_path, "rb").read()
                )
                
                logger.info("CLI OK: %d bytes", len(wav_bytes))
                return wav_bytes

            except asyncio.TimeoutError:
                last_error = EngineUnavailableError(f"Timeout ({self._settings.ENGINE_REQUEST_TIMEOUT_SEC}s)")
            except FileNotFoundError:
                last_error = EngineUnavailableError(f"Python no encontrado: {self._settings.python_bin}")
            except Exception as e:
                last_error = e
            finally:
                for p in (in_path, out_path):
                    try:
                        if os.path.exists(p):
                            os.unlink(p)
                    except OSError:
                        pass

        raise last_error or EngineUnavailableError("CLI no disponible")

    def _get_mock_stock_voices(self) -> list[dict]:
        """Voces stock mock."""
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
        logger.debug("synthesize_stock: voice_id=%s, text_len=%d", voice_id, len(text))

        voice = next((v for v in self._stock_voices if v["voice_id"] == voice_id), None)
        if not voice:
            raise VoiceNotFoundError(voice_id, "stock")

        if language not in self._languages:
            raise UnsupportedLanguageError(language, self._languages)

        if emotion and emotion not in self._emotions:
            raise UnsupportedEmotionError(emotion, self._emotions)

        async with self._semaphore:
            if self._use_mock:
                return self._generate_test_tone_wav(
                    duration_sec=max(0.5, len(text) * 0.08),
                    sample_rate=22050,
                    frequency=440.0,
                    amplitude=0.3,
                )

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
            return await self._invoke_cli(operation="synthesize_stock", payload=payload)

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
        logger.debug("synthesize_clone: ref=%s, text_len=%d", reference_audio_path, len(text))

        if language not in self._languages:
            raise UnsupportedLanguageError(language, self._languages)

        if emotion and emotion not in self._emotions:
            raise UnsupportedEmotionError(emotion, self._emotions)

        if not self._use_mock and not os.path.exists(reference_audio_path):
            raise EngineUnavailableError(f"Reference audio no encontrado: {reference_audio_path}")

        async with self._semaphore:
            if self._use_mock:
                return self._generate_test_tone_wav(
                    duration_sec=max(0.5, len(text) * 0.08),
                    sample_rate=22050,
                    frequency=880.0,
                    amplitude=0.3,
                )

            payload = {
                "text": text,
                "reference_audio_path": reference_audio_path,
                "language": language,
                "emotion": emotion,
                "intensity": intensity,
                "model_path": str(self._settings.model_path),
                "device": self._device,
            }
            return await self._invoke_cli(operation="synthesize_clone", payload=payload)

    async def list_stock_voices(self, language: str | None = None) -> list[dict]:
        """Lista voces stock."""
        voices = self._stock_voices
        if language:
            voices = [v for v in voices if v["language"] == language]
        return voices

    async def list_emotions(self) -> list[str]:
        """Lista emociones."""
        return self._emotions.copy()

    async def health_check(self) -> dict:
        """Estado del motor."""
        try:
            import torch
            gpu_available = torch.cuda.is_available()
            vram_free_mb = 0
            if gpu_available:
                vram_free_mb = torch.cuda.mem_get_info()[0] // (1024 * 1024)
        except ImportError:
            gpu_available = False
            vram_free_mb = 0

        return {
            "model_loaded": self._model is not None,
            "gpu_available": gpu_available,
            "device": self._device,
            "stock_voices_count": len(self._stock_voices),
            "vram_free_mb": vram_free_mb,
            "mode": "MOCK" if self._use_mock else "REAL",
            "cli_path": str(self._cli_path) if self._cli_path else None,
        }

    def _generate_test_tone_wav(
        self,
        duration_sec: float = 1.0,
        sample_rate: int = 22050,
        frequency: float = 440.0,
        amplitude: float = 0.3,
    ) -> bytes:
        """Genera WAV con tono senoidal."""
        num_samples = int(duration_sec * sample_rate)
        max_amplitude = 32767

        samples = []
        for i in range(num_samples):
            t = i / sample_rate
            value = amplitude * math.sin(2 * math.pi * frequency * t)
            sample = int(max_amplitude * value)
            samples.append(struct.pack('<h', sample))

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b''.join(samples))

        return buffer.getvalue()


_engine_instance: OmniVoiceEngine | None = None


async def get_engine() -> OmniVoiceEngine:
    """Obtiene la instancia singleton del motor."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OmniVoiceEngine()
        await _engine_instance.initialize()
    return _engine_instance


async def close_engine() -> None:
    """Cierra el motor."""
    global _engine_instance
    if _engine_instance is not None:
        _engine_instance = None
