"""Punto de entrada principal de OmniVoice API."""

import asyncio
import logging
import sys

# --- Configuración del Event Loop Policy ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    _EVENT_LOOP_POLICY_NAME = "WindowsProactorEventLoopPolicy"
else:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    _EVENT_LOOP_POLICY_NAME = type(asyncio.get_event_loop_policy()).__name__

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

logger.info(
    "Event loop policy configurada: platform=%s, policy=%s",
    sys.platform,
    _EVENT_LOOP_POLICY_NAME,
)


def _force_proactor_loop_factory() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        return loop
    return asyncio.new_event_loop()


from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from omnivoice_api.settings import get_settings
from omnivoice_api.core.omnivoice_engine import get_engine, close_engine
from omnivoice_api.core.cleanup import start_cleanup_task, stop_cleanup_task
from omnivoice_api.middleware import RequestIDMiddleware, APIKeyMiddleware
from omnivoice_api.api.v1 import voices, tts, conversations
from omnivoice_api.core.omnivoice_engine import SUPPORTED_EMOTIONS


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        current_loop = asyncio.get_running_loop()
        loop_class = type(current_loop).__name__
        is_proactor = sys.platform == "win32" and isinstance(current_loop, asyncio.ProactorEventLoop)
        logger.info(
            "Lifespan startup: loop class=%s, is_proactor=%s, platform=%s",
            loop_class, is_proactor, sys.platform,
        )
        if sys.platform == "win32" and not is_proactor:
            logger.warning(
                "ATENCIÓN: en Windows se requiere ProactorEventLoop para asyncio.subprocess."
            )
    except RuntimeError:
        pass

    logger.info("Application startup: inicializando engine OmniVoice...")
    try:
        engine = await get_engine()
        if engine._use_mock and engine._real_engine_error:
            logger.warning(
                "Engine en modo DEGRADADO (mock por fallback). Causa raíz: %s",
                engine._real_engine_error,
            )
        else:
            logger.info("Engine OmniVoice inicializado correctamente")
    except Exception as e:
        settings = get_settings()
        if settings.OMNIVOICE_FALLBACK_TO_MOCK:
            logger.exception(
                "Fallo inicializando engine, pero OMNIVOICE_FALLBACK_TO_MOCK=true: "
                "la API arrancará en modo degradado. Error: %s",
                e,
            )
        else:
            logger.exception("Fallo inicializando engine: %s", e)
            raise

    # Iniciar cleanup task
    settings = get_settings()
    start_cleanup_task(settings.OUTPUTS_DIR, ttl_seconds=settings.OUTPUT_TTL_SECONDS)

    yield

    # Shutdown
    stop_cleanup_task()
    logger.info("Application shutdown: cerrando engine OmniVoice...")
    await close_engine()


app = FastAPI(
    title="OmniVoice API",
    description="API REST para síntesis de voz multilingüe, clonado y conversaciones con OmniVoice (k2-fsa)",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={
        "docExpansion": "none",
        "filter": True,
        "showExtensions": True,
        "showCommonExtensions": True,
        "syntaxHighlight.theme": "agate",
    },
)

# --- Middleware ---
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(APIKeyMiddleware, api_key=settings.API_KEY)

# --- Rate limiting (slowapi) ---
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Prometheus metrics ---
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# --- Routers ---
app.include_router(voices.router, prefix="/api/v1")
app.include_router(tts.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")


@app.get("/api/v1/emotions", tags=["tts"], summary="Listar emociones soportadas")
async def list_emotions() -> list[dict]:
    """Devuelve la lista de emociones soportadas por el modelo.

    Las emociones se aplican como tags de texto (prefijos) en el contenido sintetizado.
    Ejemplo: ``[happy] ¡Qué alegría verte!``
    """
    descriptions = {
        "happy": "Tono alegre y contento",
        "sad": "Tono melancólico o triste",
        "angry": "Tono enfadado o iracundo",
        "excited": "Tono entusiasmado y enérgico",
        "calm": "Tono sereno y relajado",
        "nervous": "Tono tenso o ansioso",
        "whisper": "Voz susurrada",
        "singing": "Estilo cantado / melódico",
    }
    return [
        {"id": e, "name": e.capitalize(), "description": descriptions.get(e, "")}
        for e in SUPPORTED_EMOTIONS
    ]


@app.get("/api/v1/health", tags=["Health"])
async def health_check() -> JSONResponse:
    engine = await get_engine()
    health = await engine.health_check()
    settings = get_settings()
    degraded = health.get("mode") == "MOCK" and health.get("real_engine_error")
    return JSONResponse(
        content={
            "status": "degraded" if degraded else ("ok" if health["model_loaded"] else "degraded"),
            "version": settings.APP_VERSION,
            "device": health["device"],
            "mode": health.get("mode", "UNKNOWN"),
            "real_engine_error": health.get("real_engine_error"),
        }
    )


@app.get("/api/v1/health/live", tags=["Health"])
async def liveness() -> JSONResponse:
    return JSONResponse(content={"status": "alive"})


@app.get("/api/v1/health/ready", tags=["Health"])
async def readiness() -> JSONResponse:
    engine = await get_engine()
    health = await engine.health_check()
    from omnivoice_api.core.engine_paths import default_install_dir
    install_dir_exists = default_install_dir().exists()
    venv_python_exists = get_settings().python_bin.exists()
    ready = install_dir_exists and venv_python_exists and health["model_loaded"]
    return JSONResponse(
        content={
            "status": "ready" if ready else "not_ready",
            "checks": {
                "install_dir_exists": install_dir_exists,
                "venv_python_exists": venv_python_exists,
                "model_loaded": health["model_loaded"],
            }
        },
        status_code=200 if ready else 503,
    )


@app.get("/", tags=["Root"])
async def root() -> JSONResponse:
    return JSONResponse(
        content={
            "name": "OmniVoice API",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/api/v1/health",
        }
    )


if __name__ == "__main__":
    import uvicorn

    if sys.platform == "win32":
        uvicorn.run(
            "omnivoice_api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            loop="asyncio",
            factory=True,
        )
    else:
        uvicorn.run(
            "omnivoice_api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
        )
