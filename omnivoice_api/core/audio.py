"""Audio validation and processing utilities."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import hashlib

import numpy as np
import soundfile as sf
from loguru import logger

from omnivoice_api.core.exceptions import InvalidReferenceAudioError
from omnivoice_api.settings import get_settings


class AudioValidator:
    """Validates and processes reference audio for voice cloning."""
    
    def __init__(self):
        self._settings = get_settings()
        self._target_sample_rate = 22050  # OmniVoice standard
        self._target_channels = 1  # Mono
        self._min_duration_sec = 0.5  # Minimum reference audio duration
        self._max_duration_sec = 30.0  # Maximum reference audio duration

    async def validate_and_prepare(
        self,
        audio_path: Path | str,
        language: str,
    ) -> dict[str, Any]:
        """Validate reference audio and prepare it for voice cloning.
        
        Args:
            audio_path: Path to the reference audio file
            language: Expected language of the audio (for validation)
            
        Returns:
            dict containing:
                - processed_path: Path to the processed audio file
                - duration_sec: Duration in seconds
                - sample_rate: Sample rate in Hz
                - channels: Number of audio channels
                
        Raises:
            InvalidReferenceAudioError: If the audio is invalid for voice cloning
            FileNotFoundError: If the audio file doesn't exist
        """
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise FileNotFoundError(f"Reference audio not found: {audio_path}")
        
        try:
            # Read audio file info
            with sf.SoundFile(audio_path) as sound_file:
                sample_rate = sound_file.samplerate
                channels = sound_file.channels
                duration_sec = len(sound_file) / sample_rate
                
                # Validate duration
                if duration_sec < self._min_duration_sec:
                    raise InvalidReferenceAudioError(
                        f"Audio too short: {duration_sec:.2f}s (minimum {self._min_duration_sec}s)"
                    )
                
                if duration_sec > self._max_duration_sec:
                    raise InvalidReferenceAudioError(
                        f"Audio too long: {duration_sec:.2f}s (maximum {self._max_duration_sec}s)"
                    )
                
                # Validate sample rate (warn but don't fail - we'll resample)
                if sample_rate < 8000 or sample_rate > 48000:
                    raise InvalidReferenceAudioError(
                        f"Unusual sample rate: {sample_rate}Hz (recommended 8000-48000Hz)"
                    )
                
                # Process audio: convert to target sample rate and mono if needed
                processed_path = await self._process_audio(
                    audio_path, 
                    sample_rate, 
                    channels, 
                    duration_sec
                )
                
                return {
                    "processed_path": str(processed_path),
                    "duration_sec": duration_sec,
                    "sample_rate": sample_rate,
                    "channels": channels,
                }
                
        except sf.SoundFileError as e:
            raise InvalidReferenceAudioError(f"Invalid audio file: {e}") from e
        except Exception as e:
            if isinstance(e, InvalidReferenceAudioError):
                raise
            raise InvalidReferenceAudioError(f"Error processing audio: {e}") from e

    async def _process_audio(
        self,
        audio_path: Path,
        original_sample_rate: int,
        original_channels: int,
        duration_sec: float,
    ) -> Path:
        """Process audio to meet OmniVoice requirements.
        
        Args:
            audio_path: Path to the original audio file
            original_sample_rate: Original sample rate in Hz
            original_channels: Original number of channels
            duration_sec: Duration in seconds
            
        Returns:
            Path: Path to the processed audio file
        """
        # Load audio data
        data, samplerate = sf.read(audio_path)
        
        # Convert to mono if needed
        if original_channels > 1:
            # Average all channels for mono conversion
            if data.ndim > 1:
                data = data.mean(axis=1)
            logger.debug(
                f"Converted audio from {original_channels} channels to mono"
            )
        
        # Resample if needed
        if original_sample_rate != self._target_sample_rate:
            # Calculate resampling ratio
            ratio = self._target_sample_rate / original_sample_rate
            new_length = int(len(data) * ratio)
            
            # Use numpy for resampling (linear interpolation)
            old_indices = np.arange(len(data))
            new_indices = np.linspace(0, len(data) - 1, new_length)
            data = np.interp(new_indices, old_indices, data)
            
            logger.debug(
                f"Resampled audio from {original_sample_rate}Hz to {self._target_sample_rate}Hz"
            )
        
        # Ensure correct data type (float32 in range [-1, 1])
        if data.dtype != np.float32:
            if data.dtype.kind == 'i':  # Integer types
                # Normalize to [-1, 1] based on bit depth
                bits = np.iinfo(data.dtype).bits
                data = data.astype(np.float32) / (2**(bits-1))
            else:
                data = data.astype(np.float32)
        
        # Clip to valid range
        data = np.clip(data, -1.0, 1.0)
        
        # Generate processed file path
        storage_dir = Path(self._settings.VOICES_DIR)
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a unique filename based on original path and timestamp
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        hash_suffix = hashlib.md5(str(audio_path).encode()).hexdigest()[:8]
        processed_filename = f"reference_{timestamp}_{hash_suffix}.wav"
        processed_path = storage_dir / processed_filename
        
        # Write processed audio
        sf.write(
            processed_path,
            data,
            self._target_sample_rate,
            subtype='PCM_16',  # 16-bit PCM as per conventions
        )
        
        logger.info(
            f"Processed reference audio: {audio_path} -> {processed_path} "
            f"({self._target_sample_rate}Hz, mono, 16-bit PCM)"
        )
        
        return processed_path