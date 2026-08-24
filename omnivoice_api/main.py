"""Punto de entrada principal de la API OmniVoice."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from omnivoice_api.settings import settings


app = FastAPI(
    title="OmniVoice API",
    description="API REST para síntesis de voz con OmniVoice (k2-fsa)",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """
    Health check endpoint.

    Returns:
        JSONResponse: Estado del servicio y disponibilidad de GPU.
    """
    import torch

    gpu_available = torch.cuda.is_available()
    return JSONResponse(
        content={"status": "ok", "gpu": gpu_available},
        status_code=200,
    )


@app.get("/api/v1/health/live", tags=["Health"])
async def liveness() -> JSONResponse:
    """Liveness probe para Kubernetes."""
    return JSONResponse(content={"status": "alive"}, status_code=200)


@app.get("/api/v1/health/ready", tags=["Health"])
async def readiness() -> JSONResponse:
    """Readiness probe - verifica modelo cargado y DB accesible."""
    # TODO: Verificar modelo cargado y DB en fases posteriores
    return JSONResponse(content={"status": "ready"}, status_code=200)
