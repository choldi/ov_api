"""Service for managing cloned voices."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import soundfile as sf
from loguru import logger

from omnivoice_api.core.audio import AudioValidator
from omnivoice_api.core.exceptions import (
    InvalidReferenceAudioError,
    UnsupportedLanguageError,
)
from omnivoice_api.repositories.voice_repository import VoiceRepository
from omnivoice_api.settings import get_settings


class VoiceService:
    """Service for voice cloning operations."""

    def __init__(
        self,
        repository: VoiceRepository | None = None,
        audio_validator: AudioValidator | None = None,
    ):
        """Initialize the voice service.
        
        Args:
            repository: Voice repository instance (creates default if None)
            audio_validator: Audio validator instance (creates default if None)
        """
        self._settings = get_settings()
        self._repository = repository or VoiceRepository()
        self._audio_validator = audio_validator or AudioValidator()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the service and repository."""
        if not self._initialized:
            await self._repository.initialize()
            self._initialized = True
            logger.info("Voice service initialized")

    async def clone_voice(
        self,
        name: str,
        language: str,
        reference_audio_path: Path | str,
    ) -> str:
        """Clone a voice from reference audio.
        
        Args:
            name: Unique name for the cloned voice
            language: Language code (ISO 639-1) of the reference audio
            reference_audio_path: Path to the reference audio file
            
        Returns:
            str: The UUID of the created cloned voice
            
        Raises:
            ValueError: If a voice with the same name already exists
            UnsupportedLanguageError: If the language is not supported
            InvalidReferenceAudioError: If the reference audio is invalid
        """
        # Initialize if needed
        await self.initialize()
        
        # Validate language
        if language not in self._settings.omnilang_list:
            raise UnsupportedLanguageError(
                language, 
                self._settings.omnilang_list
            )
        
        # Validate and process reference audio
        validation_result = await self._audio_validator.validate_and_prepare(
            reference_audio_path, 
            language
        )
        
        # Store the processed audio
        processed_path = validation_result["processed_path"]
        duration_sec = validation_result["duration_sec"]
        
        # Create voice record in database
        voice_id = await self._repository.create(
            name=name,
            language=language,
            reference_path=str(processed_path),
            duration_sec=duration_sec,
            metadata={
                "original_path": str(reference_audio_path),
                "processed_path": str(processed_path),
                "sample_rate": validation_result["sample_rate"],
                "channels": validation_result["channels"],
                "language": language
            }
        )
        
        logger.info(
            f"Cloned voice '{name}' (ID: {voice_id}) from {reference_audio_path} "
            f"({duration_sec:.2f}s, {validation_result['sample_rate']}Hz)"
        )
        
        return voice_id

    async def get_voice(self, voice_id: str) -> dict:
        """Get a cloned voice by its ID.
        
        Args:
            voice_id: The UUID of the voice
            
        Returns:
            dict: Voice data
            
        Raises:
            VoiceNotFoundError: If no voice is found with the given ID
        """
        await self.initialize()
        return await self._repository.get_by_id(voice_id)

    async def get_voice_by_name(self, name: str) -> dict:
        """Get a cloned voice by its name.
        
        Args:
            name: The name of the voice
            
        Returns:
            dict: Voice data
            
        Raises:
            VoiceNotFoundError: If no voice is found with the given name
        """
        await self.initialize()
        return await self._repository.get_by_name(name)

    async def list_voices(
        self, 
        language: str | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[dict]:
        """List cloned voices with optional filtering.
        
        Args:
            language: Filter by language (ISO 639-1)
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            list[dict]: List of voice dictionaries
        """
        await self.initialize()
        return await self._repository.list(language, limit, offset)

    async def update_voice(
        self, 
        voice_id: str, 
        name: str | None = None,
        metadata: dict | None = None
    ) -> bool:
        """Update a cloned voice's metadata.
        
        Args:
            voice_id: The UUID of the voice to update
            name: New name for the voice (optional)
            metadata: New metadata to merge with existing (optional)
            
        Returns:
            bool: True if the voice was updated, False if not found
            
        Raises:
            ValueError: If the new name conflicts with an existing voice
            VoiceNotFoundError: If no voice is found with the given ID
        """
        await self.initialize()
        # First check if voice exists
        await self.get_voice(voice_id)
        return await self._repository.update(voice_id, name, metadata)

    async def delete_voice(self, voice_id: str) -> bool:
        """Delete a cloned voice by its ID.
        
        Args:
            voice_id: The UUID of the voice to delete
            
        Returns:
            bool: True if the voice was deleted, False if not found
        """
        await self.initialize()
        return await self._repository.delete(voice_id)

    async def voice_exists(self, voice_id: str) -> bool:
        """Check if a cloned voice exists by ID.
        
        Args:
            voice_id: The UUID to check
            
        Returns:
            bool: True if the voice exists
        """
        await self.initialize()
        return await self._repository.voice_exists(voice_id)