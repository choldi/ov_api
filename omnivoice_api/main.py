"""Punto de entrada principal de OmniVoice API."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from omnivoice_api.settings import get_settings
from omnivoice_api.core.omnivoice_engine import get_engine, close_engine
from omnivoice_api.api.v1 import voices, tts


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
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
# voices.router ya tiene prefix="/voices", por lo que se monta en /api/v1/voices
app.include_router(voices.router, prefix="/api/v1")
# tts.router ahora tiene prefix="/tts", por lo que se monta en /api/v1/tts
app.include_router(tts.router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """Health check completo (modelo, GPU, DB)."""
    engine = await get_engine()
    health = await engine.health_check()
    settings = get_settings()
    return JSONResponse(
        content={
            "status": "ok" if health["model_loaded"] else "degraded",
            "version": settings.APP_VERSION,
            "device": health["device"],
            "install_dir": str(settings.OMNIVOICE_INSTALL_DIR),
            "venv_dir": str(settings.OMNIVOICE_VENV_DIR),
            "python_bin": str(settings.python_bin),
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
    settings = get_settings()
    
    # Check if installation directories exist
    install_dir_exists = settings.OMNIVOICE_INSTALL_DIR.exists()
    venv_python_exists = settings.python_bin.exists()
    
    # Installation is ready if both directories exist and model is loaded
    installation_ready = install_dir_exists and venv_python_exists
    model_ready = health["model_loaded"]
    ready = installation_ready and model_ready
    
    return JSONResponse(
        content={
            "status": "ready" if ready else "not_ready",
            "checks": {
                "install_dir_exists": install_dir_exists,
                "venv_python_exists": venv_python_exists,
            }
        },
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
