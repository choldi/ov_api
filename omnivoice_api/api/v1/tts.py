"""Router para síntesis de texto a voz (TTS)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, status
from fastapi.responses import Response

from omnivoice_api.core.engine_client import AudioResult, OmniVoiceEngineClient
from omnivoice_api.core.omnivoice_engine import (
    VALID_INSTRUCT_TOKENS_EN,
    GenerationParams,
)
from omnivoice_api.core.exceptions import (
    EngineUnavailableError,
    UnsupportedInstructError,
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


def _build_generation_params(
    num_step: int,
    denoise: bool,
    guidance_scale: float,
    duration: float | None,
    preprocess_prompt: bool,
    postprocess_output: bool,
    pad_duration: float,
    fade_duration: float,
    audio_chunk_duration: float,
    audio_chunk_threshold: float,
) -> GenerationParams:
    """Construye GenerationParams desde los parámetros del endpoint."""
    return GenerationParams(
        num_step=num_step,
        denoise=denoise,
        guidance_scale=guidance_scale,
        duration=duration,
        preprocess_prompt=preprocess_prompt,
        postprocess_output=postprocess_output,
        pad_duration=pad_duration,
        fade_duration=fade_duration,
        audio_chunk_duration=audio_chunk_duration,
        audio_chunk_threshold=audio_chunk_threshold,
    )


def _handle_tts_error(e: Exception) -> None:
    """Convierte excepciones del dominio en HTTPException."""
    if isinstance(e, VoiceNotFoundError):
        detail: dict = {
            "detail": f"Voz no encontrada: {e.voice_id} ({e.voice_type})",
            "error_type": "voice_not_found",
            "voice_id": e.voice_id,
        }
        if e.valid_voice_ids:
            detail["valid_voice_ids"] = e.valid_voice_ids
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail) from e
    if isinstance(e, UnsupportedLanguageError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": f"Idioma no soportado: {e.language}",
                "error_type": "unsupported_language",
                "language": e.language,
                "supported_languages": e.supported_languages,
            },
        ) from e
    if isinstance(e, UnsupportedInstructError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "detail": str(e),
                "error_type": "unsupported_instruct",
                "invalid_items": [
                    {"token": token, "suggestion": sug}
                    for token, sug in e.invalid_items.items()
                ],
                "valid_tokens": e.valid_items,
            },
        ) from e
    if isinstance(e, EngineUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"detail": "Motor de síntesis no disponible", "error_type": "engine_unavailable"},
        ) from e
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"detail": "Error interno del servidor", "error_type": "internal_error"},
    ) from e


# --- POST /tts — Stock voices ---
@router.post(
    "",
    responses={200: {"content": {"audio/wav": {}}}},
    response_class=Response,
    summary="Sintetizar texto a voz con voz stock",
)
async def synthesize_tts(
    text: Annotated[str, Body(min_length=1, description="Texto a sintetizar")],
    voice_id: Annotated[str, Body(description="ID de la voz (ej: es-mx-male)")],
    language: Annotated[str, Body(description="Idioma del texto (ISO 639-1)")],
    speed: Annotated[float, Body(ge=0.5, le=2.0, description="Velocidad de habla")] = 1.0,
    instruct: Annotated[str | None, Body(description="Instruct personalizado (voice design libre)")] = None,
    # Generation params
    num_step: Annotated[int, Body(ge=1, le=100, description="Pasos de unmasking (mayor = mejor calidad)")] = 32,
    denoise: Annotated[bool, Body(description="Aplicar denoise para voz más limpia")] = True,
    guidance_scale: Annotated[float, Body(ge=0.0, le=10.0, description="Classifier-free guidance")] = 2.0,
    duration: Annotated[float | None, Body(ge=0.5, le=120.0, description="Duración fija en segundos (sobrescribe speed)")] = None,
    preprocess_prompt: Annotated[bool, Body(description="Preprocesar audio de referencia")] = True,
    postprocess_output: Annotated[bool, Body(description="Eliminar silencios largos del output")] = True,
    pad_duration: Annotated[float, Body(ge=0.0, le=1.0, description="Silencio por lado (segundos)")] = 0.1,
    fade_duration: Annotated[float, Body(ge=0.0, le=1.0, description="Duración fade-in/out (segundos)")] = 0.1,
    audio_chunk_duration: Annotated[float, Body(ge=1.0, le=60.0, description="Duración target por chunk (segundos)")] = 15.0,
    audio_chunk_threshold: Annotated[float, Body(ge=5.0, le=120.0, description="Umbral para activar chunking (segundos)")] = 30.0,
    accept: Annotated[str | None, Header(description="Tipo de contenido esperado")] = None,
    tts_service: TtsService = Depends(get_tts_service),
) -> Response:
    """Sintetiza texto a voz con voz stock o clonada."""
    try:
        gen_params = _build_generation_params(
            num_step, denoise, guidance_scale, duration,
            preprocess_prompt, postprocess_output, pad_duration, fade_duration,
            audio_chunk_duration, audio_chunk_threshold,
        )

        # Si se proporciona instruct, usar voice design libre
        if instruct:
            result = await tts_service.synthesize_instruct(
                text=text,
                instruct=instruct,
                language=language,
                speed=speed,
                generation_params=gen_params,
            )
        else:
            result = await tts_service.synthesize_stock(
                text=text,
                voice_id=voice_id,
                language=language,
                speed=speed,
                generation_params=gen_params,
            )
    except (VoiceNotFoundError, UnsupportedLanguageError, UnsupportedInstructError, EngineUnavailableError) as e:
        _handle_tts_error(e)
    except Exception as e:
        _handle_tts_error(e)

    media_type = "audio/wav"
    return Response(content=result.wav_bytes, media_type=media_type)


# --- POST /tts/instruct — Custom instruct ---
@router.post(
    "/instruct",
    responses={200: {"content": {"audio/wav": {}}}},
    response_class=Response,
    summary="Sintetizar texto con instruct personalizado",
    description="Voice design libre: especifica atributos del hablante directamente.",
)
async def synthesize_instruct(
    text: Annotated[str, Body(min_length=1, description="Texto a sintetizar")],
    instruct: Annotated[str, Body(description="Instruct de voice design (ej: 'female, young adult, british accent')")],
    language: Annotated[str, Body(description="Idioma del texto (ISO 639-1)")],
    speed: Annotated[float, Body(ge=0.5, le=2.0, description="Velocidad de habla")] = 1.0,
    # Generation params
    num_step: Annotated[int, Body(ge=1, le=100, description="Pasos de unmasking")] = 32,
    denoise: Annotated[bool, Body(description="Aplicar denoise")] = True,
    guidance_scale: Annotated[float, Body(ge=0.0, le=10.0, description="Classifier-free guidance")] = 2.0,
    duration: Annotated[float | None, Body(ge=0.5, le=120.0, description="Duración fija (sobrescribe speed)")] = None,
    preprocess_prompt: Annotated[bool, Body(description="Preprocesar audio de referencia")] = True,
    postprocess_output: Annotated[bool, Body(description="Eliminar silencios del output")] = True,
    pad_duration: Annotated[float, Body(ge=0.0, le=1.0, description="Silencio por lado")] = 0.1,
    fade_duration: Annotated[float, Body(ge=0.0, le=1.0, description="Fade-in/out")] = 0.1,
    audio_chunk_duration: Annotated[float, Body(ge=1.0, le=60.0, description="Duración target por chunk")] = 15.0,
    audio_chunk_threshold: Annotated[float, Body(ge=5.0, le=120.0, description="Umbral para chunking")] = 30.0,
    accept: Annotated[str | None, Header(description="Tipo de contenido esperado")] = None,
    tts_service: TtsService = Depends(get_tts_service),
) -> Response:
    """Sintetiza texto con un instruct de voice design personalizado."""
    try:
        gen_params = _build_generation_params(
            num_step, denoise, guidance_scale, duration,
            preprocess_prompt, postprocess_output, pad_duration, fade_duration,
            audio_chunk_duration, audio_chunk_threshold,
        )
        result = await tts_service.synthesize_instruct(
            text=text,
            instruct=instruct,
            language=language,
            speed=speed,
            generation_params=gen_params,
        )
    except (UnsupportedLanguageError, UnsupportedInstructError, EngineUnavailableError) as e:
        _handle_tts_error(e)
    except Exception as e:
        _handle_tts_error(e)

    return Response(content=result.wav_bytes, media_type="audio/wav")


# --- GET /tts/voice-design/tokens ---
@router.get(
    "/voice-design/tokens",
    summary="Listar tokens válidos para voice design",
    description="Devuelve los tokens de instruct agrupados por categoría.",
)
async def get_voice_design_tokens() -> dict:
    """Devuelve los tokens válidos para instruct de voice design."""
    return {
        "gender": ["male", "female"],
        "age": ["child", "teenager", "young adult", "middle-aged", "elderly"],
        "pitch": ["very low pitch", "low pitch", "moderate pitch", "high pitch", "very high pitch"],
        "style": ["whisper"],
        "english_accent": [
            "american accent", "australian accent", "british accent", "canadian accent",
            "chinese accent", "indian accent", "japanese accent", "korean accent",
            "portuguese accent", "russian accent",
        ],
        "chinese_dialect": [
            "河南话", "陕西话", "四川话", "贵州话", "云南话", "桂林话",
            "济南话", "石家庄话", "甘肃话", "宁夏话", "青岛话", "东北话",
        ],
    }
