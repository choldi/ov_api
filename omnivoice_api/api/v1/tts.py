"""Router para síntesis de texto a voz (TTS)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, status
from fastapi.responses import Response

from omnivoice_api.core.engine_client import AudioResult, OmniVoiceEngineClient
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedEmotionError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from omnivoice_api.services.tts import TtsService
from omnivoice_api.services.voice_service import VoiceService

router = APIRouter(prefix="/tts", tags=["tts"])


async def get_tts_service() -> TtsService:
    """Dependency para obtener el servicio TTS."""
    engine_client = OmniVoiceEngineClient()
    voice_service = VoiceService()
    service = TtsService(engine_client=engine_client, voice_service=voice_service)
    try:
        yield service
    finally:
        await service.close()


@router.post(
    "",
    responses={200: {"content": {"audio/wav": {}}}},
    response_class=Response,
    summary="Sintetizar texto a voz",
    description="Convierte texto en audio usando una voz stock o clonada. Soporta control de velocidad y emoción.",
)
async def synthesize_tts(
    # Parámetros del cuerpo (requeridos)
    text: Annotated[
        str,
        Body(
            min_length=1,
            description="Texto a sintetizar",
            examples=["Hola, esto es una prueba de síntesis de voz"],
        ),
    ],
    voice_id: Annotated[
        str,
        Body(
            description="ID de la voz a utilizar (ej: es-mx-male, es-es-female)",
            examples=["es-mx-male"],
        ),
    ],
    language: Annotated[
        str,
        Body(
            description="Idioma del texto (ISO 639-1, ej: es, en, fr)",
            examples=["es"],
        ),
    ],
    # Parámetros opcionales
    speed: Annotated[
        float,
        Body(ge=0.5, le=2.0, description="Velocidad de habla (0.5 a 2.0)"),
    ] = 1.0,
    emotion: Annotated[
        str | None,
        Body(
            description="Emoción a aplicar (neutral, happy, sad, angry, surprised)",
            examples=[None, "happy"],
        ),
    ] = None,
    intensity: Annotated[
        float | None,
        Body(ge=0.0, le=1.0, description="Intensidad de la emoción (0.0 a 1.0)"),
    ] = None,
    # Cabeceras opcionales
    accept: Annotated[
        str | None,
        Header(description="Tipo de contenido esperado (audio/wav o audio/mpeg)"),
    ] = None,
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
