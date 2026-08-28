"""Router para gestión de voces."""

from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, status, UploadFile
from fastapi.responses import JSONResponse

from omnivoice_api.core.engine_client import OmniVoiceEngineClient, StockVoice
from omnivoice_api.core.exceptions import (
    InvalidReferenceAudioError,
    UnsupportedLanguageError,
    VoiceNotFoundError,
)
from omnivoice_api.repositories.voice_repository import VoiceRepository
from omnivoice_api.services.voice_service import VoiceService
from omnivoice_api.settings import get_settings

router = APIRouter(prefix="/voices", tags=["voices"])


async def get_engine_client() -> OmniVoiceEngineClient:
    """Dependency para obtener el cliente del engine."""
    client = OmniVoiceEngineClient()
    await client.start()
    try:
        yield client
    finally:
        await client.stop()


async def get_voice_service() -> VoiceService:
    """Dependency para obtener el servicio de voces."""
    service = VoiceService()
    await service.initialize()
    try:
        yield service
    finally:
        pass  # Service cleanup handled elsewhere if needed


@router.get("/stock", response_model=list[StockVoice])
async def list_stock_voices(
    language: str | None = Query(None, description="Filtrar por idioma (ISO 639-1)"),
    engine_client: OmniVoiceEngineClient = Depends(get_engine_client),
) -> list[StockVoice]:
    """
    Lista las voces stock disponibles.
    
    Opcionalmente filtradas por idioma.
    """
    voices = await engine_client.list_stock_voices(language)
    return voices


@router.post("/clone", status_code=status.HTTP_201_CREATED)
async def clone_voice(
    name: str = Form(..., description="Nombre único para la voz clonada"),
    language: str = Form(..., description="Idioma del audio de referencia (ISO 639-1)"),
    reference_audio: UploadFile = File(..., description="Archivo de audio de referencia"),
    voice_service: VoiceService = Depends(get_voice_service),
) -> dict:
    """
    Clona una voz desde un archivo de audio de referencia.
    
    - **name**: Nombre único para la voz clonada
    - **language**: Idioma del audio de referencia (ISO 639-1)
    - **reference_audio**: Archivo de audio de referencia (WAV, FLAC, etc.)
    """
    # Validate file type
    if not reference_audio.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nombre de archivo requerido"
        )
    
    # Save uploaded file temporarily
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(reference_audio.filename).suffix) as tmp_file:
        content = await reference_audio.read()
        tmp_file.write(content)
        tmp_file_path = Path(tmp_file.name)
    
    try:
        # Clone the voice
        voice_id = await voice_service.clone_voice(
            name=name,
            language=language,
            reference_audio_path=tmp_file_path,
        )
        
        return {
            "voice_id": voice_id,
            "name": name,
            "language": language,
            "message": f"Voz '{name}' clonada exitosamente"
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except (UnsupportedLanguageError, InvalidReferenceAudioError) as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno: {str(e)}"
        )
    finally:
        # Clean up temporary file
        tmp_file_path.unlink(missing_ok=True)


@router.get("/cloned", response_model=List[dict])
async def list_cloned_voices(
    language: str | None = Query(None, description="Filtrar por idioma (ISO 639-1)"),
    limit: int = Query(100, ge=1, le=1000, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación"),
    voice_service: VoiceService = Depends(get_voice_service),
) -> list[dict]:
    """
    Lista las voces clonadas disponibles.
    
    - **language**: Filtrar por idioma (ISO 639-1)
    - **limit**: Número máximo de resultados (1-1000)
    - **offset**: Desplazamiento para paginación
    """
    return await voice_service.list_voices(language=language, limit=limit, offset=offset)


@router.get("/cloned/{voice_id}", response_model=dict)
async def get_cloned_voice(
    voice_id: str,
    voice_service: VoiceService = Depends(get_voice_service),
) -> dict:
    """
    Obtiene una voz clonada específica por su ID.
    
    - **voice_id**: UUID de la voz clonada
    """
    try:
        return await voice_service.get_voice(voice_id)
    except VoiceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voz clonada no encontrada: {e.voice_id}"
        )


@router.delete("/cloned/{voice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cloned_voice(
    voice_id: str,
    voice_service: VoiceService = Depends(get_voice_service),
) -> None:
    """
    Elimina una voz clonada por su ID.
    
    - **voice_id**: UUID de la voz clonada
    """
    try:
        deleted = await voice_service.delete_voice(voice_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Voz clonada no encontrada: {voice_id}"
            )
    except VoiceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voz clonada no encontrada: {e.voice_id}"
        )
