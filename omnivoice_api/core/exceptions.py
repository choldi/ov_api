"""Excepciones personalizadas de la API de OmniVoice."""

from __future__ import annotations


class OmniVoiceAPIError(Exception):
    """Excepción base para todos los errores de la API de OmniVoice."""
    pass


class VoiceNotFoundError(OmniVoiceAPIError):
    """Se lanza cuando no se encuentra una voz solicitada."""

    def __init__(self, voice_id: str, voice_type: str = "stock") -> None:
        self.voice_id = voice_id
        self.voice_type = voice_type
        super().__init__(f"Voz no encontrada: {voice_id} ({voice_type})")


class UnsupportedLanguageError(OmniVoiceAPIError):
    """Se lanza cuando se solicita un idioma no soportado."""

    def __init__(self, language: str, supported_languages: list[str]) -> None:
        self.language = language
        self.supported_languages = supported_languages
        super().__init__(
            f"Idioma no soportado: {language}. Idiomas soportados: {', '.join(supported_languages)}"
        )


class UnsupportedEmotionError(OmniVoiceAPIError):
    """Se lanza cuando se solicita una emoción no soportada."""

    def __init__(self, emotion: str, supported_emotions: list[str]) -> None:
        self.emotion = emotion
        self.supported_emotions = supported_emotions
        super().__init__(
            f"Emoción no soportada: {emotion}. Emociones soportadas: {', '.join(supported_emotions)}"
        )


class EngineUnavailableError(OmniVoiceAPIError):
    """Se lanza cuando el motor de síntesis no está disponible."""

    def __init__(self, detail: str = "Motor de síntesis no disponible") -> None:
        self.detail = detail
        super().__init__(detail)
