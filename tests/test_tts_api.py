"""Tests de integración para el endpoint TTS."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from omnivoice_api.core.engine_client import AudioResult
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedInstructError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)


def _make_wav() -> bytes:
    return (
        b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
        b"\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00"
        b"\x02\x00\x10\x00data\x00\x00\x00\x00"
    )


@pytest.mark.asyncio
async def test_tts_stock_success(async_client: AsyncClient) -> None:
    with patch("omnivoice_api.api.v1.tts.get_tts_service") as mock_dep:
        mock_service = AsyncMock()
        mock_service.synthesize_stock.return_value = AudioResult(
            wav_bytes=_make_wav(), duration_sec=0.5, sample_rate=22050,
        )
        mock_dep.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_dep.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await async_client.post(
            "/api/v1/tts",
            json={"text": "Hola", "voice_id": "es-mx-male", "language": "es"},
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tts_instruct_success(async_client: AsyncClient) -> None:
    with patch("omnivoice_api.api.v1.tts.get_tts_service") as mock_dep:
        mock_service = AsyncMock()
        mock_service.synthesize_instruct.return_value = AudioResult(
            wav_bytes=_make_wav(), duration_sec=0.5, sample_rate=22050,
        )
        mock_dep.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_dep.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await async_client.post(
            "/api/v1/tts",
            json={"text": "Hello", "voice_id": "es-mx-male", "language": "en", "instruct": "female, british accent"},
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tts_voice_not_found(async_client: AsyncClient) -> None:
    with patch("omnivoice_api.api.v1.tts.get_tts_service") as mock_dep:
        mock_service = AsyncMock()
        err = VoiceNotFoundError("nonexistent", "stock")
        err.valid_voice_ids = ["es-mx-male", "en-us-male"]
        mock_service.synthesize_stock.side_effect = err
        mock_dep.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_dep.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await async_client.post(
            "/api/v1/tts",
            json={"text": "Hola", "voice_id": "nonexistent", "language": "es"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tts_unsupported_language(async_client: AsyncClient) -> None:
    with patch("omnivoice_api.api.v1.tts.TtsService") as MockService:
        mock_service = AsyncMock()
        mock_service.synthesize_stock = AsyncMock(side_effect=UnsupportedLanguageError("xx", ["es", "en"]))
        mock_service.close = AsyncMock()
        MockService.return_value = mock_service

        resp = await async_client.post(
            "/api/v1/tts",
            json={"text": "Hola", "voice_id": "es-mx-male", "language": "xx"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_tts_instruct_endpoint_invalid(async_client: AsyncClient) -> None:
    with patch("omnivoice_api.api.v1.tts.get_tts_service") as mock_dep:
        mock_service = AsyncMock()
        mock_service.synthesize_instruct.side_effect = UnsupportedInstructError(
            "Mexican accent", {"mexican accent": None}, ["male", "female"],
        )
        mock_dep.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_dep.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await async_client.post(
            "/api/v1/tts/instruct",
            json={"text": "Hello", "instruct": "Mexican accent", "language": "en"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_tts_voice_design_tokens(async_client: AsyncClient) -> None:
    resp = await async_client.get("/api/v1/tts/voice-design/tokens")
    assert resp.status_code == 200
    data = resp.json()
    assert "gender" in data
    assert "male" in data["gender"]
    assert "english_accent" in data
    assert "chinese_dialect" in data
