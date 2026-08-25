"""Punto de entrada principal de la API OmniVoice.

La API NO carga el modelo OmniVoice en su propio proceso. En su lugar, valida
que la instalación externa existe y deja que el ``EngineClient`` (Sprint 1)
gestione el subprocess.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from omnivoice_api.core.engine_paths import validate_installation
from omnivoice_api.settings import settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida de la aplicación."""
    # --- Startup ---
    logger.info(
        "startup",
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        device=settings.OMNIVOICE_DEVICE,
        install_dir=str(settings.OMNIVOICE_INSTALL_DIR),
        venv_dir=str(settings.OMNIVOICE_VENV_DIR),
    )

    # Validar instalación externa de OmniVoice (no lanza; sólo registra)
    try:
        python_bin = validate_installation(
            install_dir=settings.OMNIVOICE_INSTALL_DIR,
            venv_dir=settings.OMNIVOICE_VENV_DIR,
        )
        logger.info("omnivoice_install_ok", python_bin=str(python_bin))
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "omnivoice_install_failed",
            error=str(exc),
            install_dir=str(settings.OMNIVOICE_INSTALL_DIR),
        )
        # No abortamos el arranque: /health/ready informará del problema.

    yield

    # --- Shutdown ---
    logger.info("shutdown", app=settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "API REST para síntesis de voz con OmniVoice (k2-fsa). "
        "Consume una instalación externa del engine."
    ),
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
    """Health check general: estado del servicio + info de paths externos."""
    return JSONResponse(
        content={
            "status": "ok",
            "version": settings.APP_VERSION,
            "device": settings.OMNIVOICE_DEVICE,
            "install_dir": str(settings.OMNIVOICE_INSTALL_DIR),
            "venv_dir": str(settings.OMNIVOICE_VENV_DIR),
            "python_bin": str(settings.OMNIVOICE_PYTHON_BIN),
        },
        status_code=200,
    )


@app.get("/api/v1/health/live", tags=["Health"])
async def liveness() -> JSONResponse:
    """Liveness probe: el proceso responde."""
    return JSONResponse(content={"status": "alive"}, status_code=200)


@app.get("/api/v1/health/ready", tags=["Health"])
async def readiness() -> JSONResponse:
    """Readiness probe: la instalación externa de OmniVoice es utilizable."""
    checks: dict[str, bool | str] = {
        "install_dir_exists": False,
        "venv_python_exists": False,
    }
    all_ready = False
    try:
        python_bin = validate_installation(
            install_dir=settings.OMNIVOICE_INSTALL_DIR,
            venv_dir=settings.OMNIVOICE_VENV_DIR,
        )
        checks["install_dir_exists"] = True
        checks["venv_python_exists"] = True
        checks["python_bin"] = str(python_bin)
        all_ready = True
    except Exception as exc:  # noqa: BLE001
        checks["error"] = str(exc)

    return JSONResponse(
        content={"status": "ready" if all_ready else "not_ready", "checks": checks},
        status_code=200 if all_ready else 503,
    )

