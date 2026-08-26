"""Punto de entrada principal de OmniVoice API."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from omnivoice_api.settings import get_settings
from omnivoice_api.core.omnivoice_engine import get_engine, close_engine
from omnivoice_api.api.v1 import voices, tts

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await get_engine()  # Inicializa el engine (warmup incluido)
    yield
    # Shutdown
    await close_engine()


app = FastAPI(
    title="OmniVoice API",
    description="API REST para síntesis de voz multilingüe, clonado y conversaciones con OmniVoice (k2-fsa)",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(voices.router, prefix="/api/v1")
app.include_router(tts.router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Health check completo (modelo, GPU, DB)."""
    engine = await get_engine()
    health = await engine.health_check()
    return JSONResponse(
        content={
            "status": "ok" if health["model_loaded"] else "degraded",
            "gpu": health["gpu_available"],
            "model_loaded": health["model_loaded"],
            "device": health["device"],
            "stock_voices": health["stock_voices_count"],
        }
    )


@app.get("/api/v1/health/live", tags=["Health"])
async def liveness() -> JSONResponse:
    """Liveness probe (Kubernetes)."""
    return JSONResponse(content={"status": "alive"})


@app.get("/api/v1/health/ready", tags=["Health"])
async def readiness() -> JSONResponse:
    """Readiness probe (Kubernetes)."""
    engine = await get_engine()
    health = await engine.health_check()
    ready = health["model_loaded"]
    return JSONResponse(
        content={"status": "ready" if ready else "not ready", "model_loaded": ready},
        status_code=200 if ready else 503,
    )


@app.get("/", tags=["Root"])
async def root() -> JSONResponse:
    """Endpoint raíz con información básica."""
    return JSONResponse(
        content={
            "name": "OmniVoice API",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }
    )
