"""Factory for creating TTS engine instances based on TTS_ENGINE setting."""

from __future__ import annotations

import json
import logging

from omnivoice_api.core.engine_base import TtsEngineBase
from omnivoice_api.settings import get_settings

logger = logging.getLogger(__name__)


def _create_single_engine(name: str) -> TtsEngineBase:
    """Create a single engine instance by name."""
    name = name.lower().strip()

    if name == "mock":
        from omnivoice_api.core.engines.mock_engine import MockEngine

        return MockEngine()

    if name == "pocket_tts":
        from omnivoice_api.core.engines.pocket_tts_engine import PocketTTSEngine

        return PocketTTSEngine()

    if name == "edgetts":
        from omnivoice_api.core.engines.edgetts_engine import EdgeTTSEngine

        return EdgeTTSEngine()

    if name == "omnivoice":
        from omnivoice_api.core.engines.omnivoice_engine_adapter import OmniVoiceAdapter

        return OmniVoiceAdapter()

    raise ValueError(f"Engine desconocido: '{name}'")


def _create_routed_engine(routing_json: str) -> TtsEngineBase:
    """Create a RoutedEngine from a JSON routing configuration.

    The routing JSON maps language codes to engine names:
        {"es":"pocket_tts","en":"pocket_tts","ca":"edgetts","_default":"pocket_tts"}
    """
    from omnivoice_api.core.engines.routed_engine import RoutedEngine

    if not routing_json or not routing_json.strip():
        raise ValueError(
            "TTS_ENGINE=routed requiere TTS_ENGINES con el mapeo JSON de idiomas. "
            'Ejemplo: TTS_ENGINES=\'{"es":"pocket_tts","ca":"edgetts","_default":"pocket_tts"}\''
        )

    try:
        routing = json.loads(routing_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"TTS_ENGINES no es JSON válido: {e}") from e

    if not isinstance(routing, dict):
        raise ValueError("TTS_ENGINES debe ser un dict JSON {idioma: engine_name}")

    # Collect unique engine names needed
    engine_names: set[str] = set(routing.values())
    engine_names.discard("_default")

    if not engine_names:
        raise ValueError("TTS_ENGINES no contiene ningún engine válido")

    # Create engine instances (one per unique engine name)
    engines: dict[str, TtsEngineBase] = {}
    for name in engine_names:
        engines[name] = _create_single_engine(name)

    logger.info(
        "Created routed engine: routing=%s, sub-engines=%s",
        routing,
        list(engines.keys()),
    )

    return RoutedEngine(engines=engines, routing=routing)


def create_engine(engine_name: str | None = None) -> TtsEngineBase:
    """Create and return a TTS engine instance.

    Args:
        engine_name: Engine identifier. If None, reads from TTS_ENGINE env var.

    Returns:
        An initialized TtsEngineBase implementation.

    Raises:
        ValueError: If the engine name is not recognized.
    """
    if engine_name is None:
        settings = get_settings()
        engine_name = settings.TTS_ENGINE

    engine_name = engine_name.lower().strip()

    if engine_name == "routed":
        settings = get_settings()
        return _create_routed_engine(settings.TTS_ENGINES)

    return _create_single_engine(engine_name)
