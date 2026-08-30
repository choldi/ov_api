"""Tests unitarios para el servicio de voces."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from omnivoice_api.core.audio import AudioValidator
from omnivoice_api.core.exceptions import (
    InvalidReferenceAudioError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from omnivoice_api.repositories.voice_repository import VoiceRepository
from omnivoice_api.services.voice_service import VoiceService


@pytest.fixture
def mock_repository() -> AsyncMock:
    """Repositorio mockeado."""
    repo = AsyncMock(spec=VoiceRepository)
    return repo


@pytest.fixture
def mock_audio_validator() -> AsyncMock:
    """Validador de audio mockeado."""
    validator = AsyncMock(spec=AudioValidator)
    return validator


@pytest.fixture
def voice_service(mock_repository: AsyncMock, mock_audio_validator: AsyncMock) -> VoiceService:
    """Servicio de voces con dependencias mockeadas."""
    with patch("omnivoice_api.services.voice_service.get_settings") as mock_settings:
        mock_settings.return_value.omnilang_list = ["es", "en", "zh"]
        service = VoiceService(
            repository=mock_repository,
            audio_validator=mock_audio_validator,
        )
        service._initialized = True  # Skip initialize
        return service


@pytest.mark.asyncio
async def test_clone_voice_success(voice_service: VoiceService, mock_repository: AsyncMock, mock_audio_validator: AsyncMock) -> None:
    """Test de clonación exitosa."""
    mock_audio_validator.validate_and_prepare.return_value = {
        "processed_path": "/tmp/processed.wav",
        "duration_sec": 5.0,
        "sample_rate": 22050,
        "channels": 1,
    }
    mock_repository.create.return_value = str(uuid4())

    voice_id = await voice_service.clone_voice(
        name="test-voice",
        language="es",
        reference_audio_path="/path/to/audio.wav",
    )
    assert voice_id is not None
    mock_repository.create.assert_called_once()


@pytest.mark.asyncio
async def test_clone_voice_unsupported_language(voice_service: VoiceService) -> None:
    """Test de error con idioma no soportado."""
    with pytest.raises(UnsupportedLanguageError):
        await voice_service.clone_voice(
            name="test-voice",
            language="xx",
            reference_audio_path="/path/to/audio.wav",
        )


@pytest.mark.asyncio
async def test_clone_voice_invalid_audio(voice_service: VoiceService, mock_audio_validator: AsyncMock) -> None:
    """Test de error con audio inválido."""
    mock_audio_validator.validate_and_prepare.side_effect = InvalidReferenceAudioError("Bad audio")
    with pytest.raises(InvalidReferenceAudioError):
        await voice_service.clone_voice(
            name="test-voice",
            language="es",
            reference_audio_path="/path/to/bad.wav",
        )


@pytest.mark.asyncio
async def test_get_voice(voice_service: VoiceService, mock_repository: AsyncMock) -> None:
    """Test de obtener voz."""
    mock_repository.get_by_id.return_value = {"id": "test-id", "name": "test"}
    voice = await voice_service.get_voice("test-id")
    assert voice["id"] == "test-id"


@pytest.mark.asyncio
async def test_get_voice_not_found(voice_service: VoiceService, mock_repository: AsyncMock) -> None:
    """Test de obtener voz no encontrada."""
    mock_repository.get_by_id.side_effect = VoiceNotFoundError("test-id")
    with pytest.raises(VoiceNotFoundError):
        await voice_service.get_voice("test-id")


@pytest.mark.asyncio
async def test_get_voice_by_name(voice_service: VoiceService, mock_repository: AsyncMock) -> None:
    """Test de obtener voz por nombre."""
    mock_repository.get_by_name.return_value = {"id": "test-id", "name": "test"}
    voice = await voice_service.get_voice_by_name("test")
    assert voice["name"] == "test"


@pytest.mark.asyncio
async def test_list_voices(voice_service: VoiceService, mock_repository: AsyncMock) -> None:
    """Test de listar voces."""
    mock_repository.list.return_value = [{"id": "1"}, {"id": "2"}]
    voices = await voice_service.list_voices(language="es", limit=10, offset=0)
    assert len(voices) == 2
    mock_repository.list.assert_called_once_with("es", 10, 0)


@pytest.mark.asyncio
async def test_update_voice(voice_service: VoiceService, mock_repository: AsyncMock) -> None:
    """Test de actualizar voz."""
    mock_repository.get_by_id.return_value = {"id": "test-id", "name": "old"}
    mock_repository.update.return_value = True
    result = await voice_service.update_voice("test-id", name="new")
    assert result is True


@pytest.mark.asyncio
async def test_delete_voice(voice_service: VoiceService, mock_repository: AsyncMock) -> None:
    """Test de eliminar voz."""
    mock_repository.delete.return_value = True
    result = await voice_service.delete_voice("test-id")
    assert result is True


@pytest.mark.asyncio
async def test_voice_exists(voice_service: VoiceService, mock_repository: AsyncMock) -> None:
    """Test de verificar existencia."""
    mock_repository.voice_exists.return_value = True
    assert await voice_service.voice_exists("test-id") is True


@pytest.mark.asyncio
async def test_initialize_calls_repository() -> None:
    """Test de que initialize inicializa el repositorio."""
    with patch("omnivoice_api.services.voice_service.get_settings") as mock_settings:
        mock_settings.return_value.omnilang_list = ["es"]
        mock_repo = AsyncMock(spec=VoiceRepository)
        mock_validator = AsyncMock(spec=AudioValidator)
        service = VoiceService(repository=mock_repo, audio_validator=mock_validator)
        await service.initialize()
        mock_repo.initialize.assert_called_once()
        assert service._initialized is True


@pytest.mark.asyncio
async def test_initialize_idempotent() -> None:
    """Test de que initialize es idempotente."""
    with patch("omnivoice_api.services.voice_service.get_settings") as mock_settings:
        mock_settings.return_value.omnilang_list = ["es"]
        mock_repo = AsyncMock(spec=VoiceRepository)
        service = VoiceService(repository=mock_repo, audio_validator=AsyncMock())
        service._initialized = True
        await service.initialize()
        mock_repo.initialize.assert_not_called()
