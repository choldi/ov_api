"""Service for voice cloning operations."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Optional

import soundfile as sf
from loguru import logger

from omnivoice_api.core.audio import AudioValidator
from omnivoice_api.core.embedding_cache import EmbeddingCache, get_embedding_cache
from omnivoice_api.core.exceptions import (
    InvalidReferenceAudioError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from omnivoice_api.repositories.voice_repository import VoiceRepository
from omnivoice_api.settings import get_settings


class VoiceService:
    """Service for voice cloning operations."""

    def __init__(
        self,
        repository: VoiceRepository | None = None,
        audio_validator: AudioValidator | None = None,
        embedding_cache: EmbeddingCache | None = None,
    ) -> None:
        self._settings = get_settings()
        self._repository = repository
        self._audio_validator = audio_validator
        self._embedding_cache = embedding_cache

    async def initialize(self) -> None:
        """Initialize the service and its dependencies."""
        if self._repository is None:
            self._repository = VoiceRepository()
            await self._repository.initialize()
        
        if self._audio_validator is None:
            self._audio_validator = AudioValidator()
        
        if self._embedding_cache is None:
            self._embedding_cache = get_embedding_cache()

    async def clone_voice(
        self,
        name: str,
        language: str,
        reference_audio_path: Path | str,
    ) -> str:
        """Clone a voice from reference audio.
        
        Args:
            name: Unique name for the cloned voice
            language: Language code (ISO 639-1)
            reference_audio_path: Path to the reference audio file
            
        Returns:
            str: The UUID of the cloned voice
            
        Raises:
            ValueError: If voice name already exists
            UnsupportedLanguageError: If language is not supported
            InvalidReferenceAudioError: If reference audio is invalid
        """
        # Validate language
        if language not in self._settings.omnilang_list:
            raise UnsupportedLanguageError(language, self._settings.omnilang_list)
        
        # Validate and prepare reference audio
        validated_path, duration_sec = await self._audio_validator.validate_and_prepare(
            reference_audio_path, language
        )
        
        # Check max duration
        if duration_sec > self._settings.MAX_REFERENCE_DURATION_SEC:
            raise InvalidReferenceAudioError(
                f"Reference audio too long: {duration_sec:.1f}s > {self._settings.MAX_REFERENCE_DURATION_SEC}s"
            )
        
        # Copy to permanent storage
        voices_dir = self._settings.VOICES_DIR
        voices_dir.mkdir(parents=True, exist_ok=True)
        
        voice_id = str(uuid.uuid4())
        dest_path = voices_dir / voice_id / "reference.wav"
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(validated_path, dest_path)
        
        # Store in repository
        voice_id = await self._repository.create(
            name=name,
            language=language,
            reference_path=str(dest_path),
            duration_sec=duration_sec,
            metadata={"original_path": str(reference_audio_path)},
        )
        
        # Pre-compute and cache embedding
        try:
            # TODO: Compute actual embedding when engine supports it
            # For now, just invalidate any existing cache entry
            self._embedding_cache.invalidate(dest_path)
        except Exception as e:
            logger.warning(f"Failed to precompute embedding for {voice_id}: {e}")
        
        logger.info(f"Voice cloned successfully: {name} ({voice_id})")
        return voice_id

    async def get_voice(self, voice_id: str) -> dict:
        """Get a cloned voice by ID."""
        return await self._repository.get_by_id(voice_id)

    async def list_voices(
        self, 
        language: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        """List cloned voices with optional filtering."""
        return await self._repository.list(language=language, limit=limit, offset=offset)

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a cloned voice."""
        # Get voice info first to delete file
        try:
            voice = await self._repository.get_by_id(voice_id)
            ref_path = Path(voice["reference_path"])
            if ref_path.exists():
                # Delete the voice directory
                shutil.rmtree(ref_path.parent, ignore_errors=True)
        except VoiceNotFoundError:
            pass
        
        # Delete from repository
        deleted = await self._repository.delete(voice_id)
        
        # Invalidate cache
        if deleted:
            self._embedding_cache.invalidate(voice_id)
        
        return deleted

    async def voice_exists(self, voice_id: str) -> bool:
        """Check if a voice exists."""
        return await self._repository.voice_exists(voice_id)
