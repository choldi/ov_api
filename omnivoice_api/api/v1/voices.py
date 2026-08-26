"""Router para gestión de voces."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from omnivoice_api.core.engine_client import OmniVoiceEngineClient, StockVoice
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
