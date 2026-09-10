"""Tests para conversaciones multi-voz."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from omnivoice_api.core.engine_client import AudioResult, OmniVoiceEngineClient, StockVoice
from omnivoice_api.core.exceptions import VoiceNotFoundError
from omnivoice_api.services.conversation import ConversationService, ConversationTurn


def _make_wav() -> bytes:
    return (
        b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00"
        b"\x01\x00\x01\x00\x44\xac\x00\x00\x88\x58\x01\x00"
        b"\x02\x00\x10\x00data\x00\x00\x00\x00"
    )


# --- Unit tests for ConversationService ---


@pytest.mark.asyncio
async def test_conversation_minimum_turns():
    service = ConversationService(engine_client=AsyncMock())
    with pytest.raises(ValueError, match="al menos 2 turnos"):
        await service.generate(turns=[ConversationTurn(voice_id="a", text="hi")])


@pytest.mark.asyncio
async def test_conversation_empty_text():
    mock_client = AsyncMock()
    mock_client.list_stock_voices = AsyncMock(return_value=[
        StockVoice(voice_id="es-mx-male", language="es", gender="male", name="C"),
    ])
    service = ConversationService(engine_client=mock_client)
    with pytest.raises(ValueError, match="texto vacío"):
        await service.generate(turns=[
            ConversationTurn(voice_id="es-mx-male", text=""),
            ConversationTurn(voice_id="es-mx-male", text="hello"),
        ])


@pytest.mark.asyncio
async def test_conversation_voice_not_found():
    mock_client = AsyncMock()
    mock_client.list_stock_voices = AsyncMock(return_value=[])
    service = ConversationService(engine_client=mock_client)
    with pytest.raises(VoiceNotFoundError):
        await service.generate(turns=[
            ConversationTurn(voice_id="nonexistent", text="hello"),
            ConversationTurn(voice_id="nonexistent", text="world"),
        ])


@pytest.mark.asyncio
async def test_conversation_success():
    mock_client = AsyncMock()
    mock_client.list_stock_voices = AsyncMock(return_value=[
        StockVoice(voice_id="es-mx-male", language="es", gender="male", name="C"),
        StockVoice(voice_id="es-mx-female", language="es", gender="female", name="A"),
    ])
    mock_client.synthesize_stock = AsyncMock(return_value=AudioResult(
        wav_bytes=_make_wav(), duration_sec=0.5, sample_rate=22050,
    ))
    service = ConversationService(engine_client=mock_client)

    result = await service.generate(turns=[
        ConversationTurn(voice_id="es-mx-male", text="Hola"),
        ConversationTurn(voice_id="es-mx-female", text="¿Qué tal?"),
    ])

    assert isinstance(result, AudioResult)
    assert result.wav_bytes[:4] == b"RIFF"
    assert mock_client.synthesize_stock.call_count == 2


@pytest.mark.asyncio
async def test_conversation_multiple_turns():
    mock_client = AsyncMock()
    mock_client.list_stock_voices = AsyncMock(return_value=[
        StockVoice(voice_id="v1", language="es", gender="male", name="A"),
        StockVoice(voice_id="v2", language="es", gender="female", name="B"),
        StockVoice(voice_id="v3", language="en", gender="male", name="C"),
    ])
    mock_client.synthesize_stock = AsyncMock(return_value=AudioResult(
        wav_bytes=_make_wav(), duration_sec=0.5, sample_rate=22050,
    ))
    service = ConversationService(engine_client=mock_client)

    result = await service.generate(turns=[
        ConversationTurn(voice_id="v1", text="First"),
        ConversationTurn(voice_id="v2", text="Second"),
        ConversationTurn(voice_id="v3", text="Third"),
    ])

    assert isinstance(result, AudioResult)
    assert mock_client.synthesize_stock.call_count == 3


@pytest.mark.asyncio
async def test_conversation_concatenation():
    """Verify that the concatenated WAV is larger than a single segment."""
    mock_client = AsyncMock()
    mock_client.list_stock_voices = AsyncMock(return_value=[
        StockVoice(voice_id="v1", language="es", gender="male", name="A"),
        StockVoice(voice_id="v2", language="es", gender="female", name="B"),
    ])
    # Return WAV with actual silence frames
    import io
    import wave
    import struct

    def make_real_wav(duration_sec: float = 0.1, sample_rate: int = 22050) -> bytes:
        n = int(duration_sec * sample_rate)
        frames = struct.pack(f"<{n}h", *([1000] * n))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(frames)
        return buf.getvalue()

    wav1 = make_real_wav(0.1)
    wav2 = make_real_wav(0.1)

    mock_client.synthesize_stock = AsyncMock(side_effect=[
        AudioResult(wav_bytes=wav1, duration_sec=0.1, sample_rate=22050),
        AudioResult(wav_bytes=wav2, duration_sec=0.1, sample_rate=22050),
    ])
    service = ConversationService(engine_client=mock_client)

    result = await service.generate(
        turns=[
            ConversationTurn(voice_id="v1", text="First"),
            ConversationTurn(voice_id="v2", text="Second"),
        ],
        pause_ms=200,
    )

    # With 300ms pause, total should be > 2 * 0.1s
    # Verify the result is valid WAV
    assert result.wav_bytes[:4] == b"RIFF"
    assert len(result.wav_bytes) > len(wav1) + len(wav2)


# --- API tests ---


@pytest.mark.asyncio
async def test_conversations_endpoint_success(async_client):
    with patch("omnivoice_api.api.v1.conversations.get_conversation_service") as mock_dep:
        mock_service = AsyncMock()
        mock_service.generate.return_value = AudioResult(
            wav_bytes=_make_wav(), duration_sec=1.0, sample_rate=22050,
        )
        mock_dep.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_dep.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await async_client.post(
            "/api/v1/conversations",
            json={
                "turns": [
                    {"voice_id": "es-mx-male", "text": "Hola"},
                    {"voice_id": "es-mx-female", "text": "¿Qué tal?"},
                ],
                "pause_ms": 300,
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "audio/wav"


@pytest.mark.asyncio
async def test_conversations_endpoint_too_few_turns(async_client):
    resp = await async_client.post(
        "/api/v1/conversations",
        json={
            "turns": [{"voice_id": "es-mx-male", "text": "Solo uno"}],
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_conversations_endpoint_empty_text(async_client):
    resp = await async_client.post(
        "/api/v1/conversations",
        json={
            "turns": [
                {"voice_id": "es-mx-male", "text": ""},
                {"voice_id": "es-mx-female", "text": "Hello"},
            ],
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_conversations_endpoint_missing_fields(async_client):
    resp = await async_client.post(
        "/api/v1/conversations",
        json={
            "turns": [
                {"voice_id": "es-mx-male"},  # missing text
                {"text": "Hello"},  # missing voice_id
            ],
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_conversations_endpoint_voice_not_found(async_client):
    with patch("omnivoice_api.api.v1.conversations.get_conversation_service") as mock_dep:
        mock_service = AsyncMock()
        mock_service.generate.side_effect = VoiceNotFoundError("nonexistent", "stock")
        mock_dep.return_value.__aenter__ = AsyncMock(return_value=mock_service)
        mock_dep.return_value.__aexit__ = AsyncMock(return_value=False)

        resp = await async_client.post(
            "/api/v1/conversations",
            json={
                "turns": [
                    {"voice_id": "nonexistent", "text": "Hello"},
                    {"voice_id": "es-mx-female", "text": "World"},
                ],
            },
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_conversations_endpoint_custom_pause(async_client):
    with patch("omnivoice_api.services.conversation.ConversationService.generate") as mock_gen:
        mock_gen.return_value = AudioResult(
            wav_bytes=_make_wav(), duration_sec=1.0, sample_rate=22050,
        )
        resp = await async_client.post(
            "/api/v1/conversations",
            json={
                "turns": [
                    {"voice_id": "es-mx-male", "text": "First"},
                    {"voice_id": "es-mx-female", "text": "Second"},
                ],
                "pause_ms": 1000,
            },
        )
        assert resp.status_code == 200
        mock_gen.assert_called_once()
