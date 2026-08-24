"""Punto de entrada principal de la API OmniVoice."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from omnivoice_api.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación."""
    # Startup
    import torch
    print(f"🚀 Iniciando {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"   Device: {settings.OMNIVOICE_DEVICE}")
    print(f"   CUDA disponible: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"   GPU: {torch.cuda.get_device_name(0)}")
        print(f"   VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    
    # Warm-up del modelo se hará en Sprint 1
    
    yield
    
    # Shutdown
    print("🛑 Apagando OmniVoice API")


app = FastAPI(
    title=settings.APP_NAME,
    description="API REST para síntesis de voz con OmniVoice (k2-fsa)",
    version=settings.APP_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    gpu_info = {}
    if gpu_available:
        gpu_info = {
            "device_name": torch.cuda.get_device_name(0),
            "vram_total_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 1),
            "vram_allocated_gb": round(torch.cuda.memory_allocated(0) / 1e9, 2),
            "vram_reserved_gb": round(torch.cuda.memory_reserved(0) / 1e9, 2),
        }
    
    return JSONResponse(
        content={
            "status": "ok",
            "version": settings.APP_VERSION,
            "gpu": gpu_available,
            "gpu_info": gpu_info,
            "device": settings.OMNIVOICE_DEVICE,
        },
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
    checks = {
        "model_loaded": False,  # Sprint 1
        "database_accessible": False,  # Sprint 2
    }
    all_ready = all(checks.values())
    
    return JSONResponse(
        content={"status": "ready" if all_ready else "not_ready", "checks": checks},
        status_code=200 if all_ready else 503,
    )
