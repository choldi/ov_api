"""Router para síntesis de texto a voz (TTS)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, status
from fastapi.responses import Response

from omnivoice_api.core.engine_client import AudioResult
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from omnivoice_api.settings import get_settings
from omnivoice_api.services.tts import TtsService

router = APIRouter(tags=["tts"])


async def get_tts_service() -> TtsService:
        """Dependency para obtener el servicio TTS."""
        engine_client = OmniVoiceEngineClient()
        voice_service = VoiceService()
        service = TtsService(engine_client=engine_client, voice_service=voice_service)
        try:
            yield service
        finally:
            await service.close()


@router.post("/tts", responses={200: {"content": {"audio/wav": {}}}}, response_class=Response)
async def synthesize_tts(
    request: Request,
    # Parámetros del cuerpo (requeridos)
    text: Annotated[str, Body(min_length=1, description="Texto a sintetizar")],
    voice_id: Annotated[str, Body(description="ID de la voz a utilizar")],
    language: Annotated[str, Body(description="Idioma del texto (ISO 639-1)")],
    # Parámetros opcionales
    speed: Annotated[float, Body(ge=0.5, le=2.0, description="Velocidad de habla")] = 1.0,
    emotion: Annotated[str | None, Body(description="Emoción a aplicar")] = None,
    intensity: Annotated[float | None, Body(ge=0.0, le=1.0, description="Intensidad de la emoción")] = None,
    # Cabeceras opcionales
    accept: Annotated[str | None, Header(description="Tipo de contenido esperado")] = None,
    # Dependencias
    tts_service: TtsService = Depends(get_tts_service),
) -> Response:
    """
    Sintetiza texto a voz.
    
    Devuelve audio en formato WAV por defecto.
    """
    try:
        result = await tts_service.synthesize_stock(
            text=text,
            voice_id=voice_id,
            language=language,
            speed=speed,
            emotion=emotion,
            intensity=intensity,
        )
    except VoiceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voz no encontrada: {e.voice_id} ({e.voice_type})",
        ) from e
    except UnsupportedLanguageError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Idioma no soportado: {e.language}. Idiomas soportados: {', '.join(e.supported_languages)}",
        ) from e
    except UnsupportedEmotionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Emoción no soportada: {e.emotion}. Emociones soportadas: {', '.join(e.supported_emotions)}",
        ) from e
    except EngineUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Motor de síntesis no disponible",
        ) from e
    except Exception as e:
        # Log interno (en producción usar structlog)
        print(f"Error inesperado en TTS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor",
        ) from e

    # Determinar tipo de contenido
    media_type = "audio/wav"
    if accept and "audio/mpeg" in accept:
        # TODO: Convertir WAV a MP3 si se solicita
        # Por ahora, devolvemos WAV incluso si se solicita MP3
        pass

    return Response(content=result.wav_bytes, media_type=media_type)
