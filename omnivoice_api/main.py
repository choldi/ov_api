"""Punto de entrada principal de OmniVoice API."""

import asyncio
import logging
import sys

# --- Configuración del Event Loop Policy ---
# En Windows, el SelectorEventLoop (default de uvicorn) NO soporta subprocesses
# (asyncio.create_subprocess_exec -> NotImplementedError). El engine invoca el
# CLI de OmniVoice vía subprocess, por lo que forzamos ProactorEventLoop.
# En Linux/Unix, el SelectorEventLoop por defecto sí soporta subprocess_exec,
# pero lo fijamos explícitamente para tener un comportamiento determinista.
# Debe ejecutarse ANTES de que uvicorn cree el event loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    _EVENT_LOOP_POLICY_NAME = "WindowsProactorEventLoopPolicy"
else:
    # En Unix/Linux, el default es SelectorEventLoop que sí soporta subprocess_exec.
    # Lo fijamos explícitamente para ser deterministas.
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    _EVENT_LOOP_POLICY_NAME = type(asyncio.get_event_loop_policy()).__name__

# Configurar logging básico temprano para que los logs de diagnóstico
# del engine sean visibles incluso si falla el arranque.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

# Log de diagnóstico: confirmar la política de event loop aplicada
logger.info(
    "Event loop policy configurada: platform=%s, policy=%s. "
    "Esta política es necesaria para soportar asyncio.subprocess "
    "(requerido por el engine OmniVoice).",
    sys.platform,
    _EVENT_LOOP_POLICY_NAME,
)


def _force_proactor_loop_factory():
    """
    Devuelve un loop_factory que fuerza ProactorEventLoop en Windows.

    Esto es necesario porque en algunas versiones de uvicorn, aunque se
    haya instalado WindowsProactorEventLoopPolicy, uvicorn crea su propio
    loop usando SelectorEventLoop. Este factory se pasa a uvicorn vía
    `loop_factory=...` para garantizar que el loop creado sea Proactor.

    En Linux/Unix devuelve None (uvicorn usa el default).
    """
    if sys.platform == "win32":
        logger.info(
            "Proporcionando loop_factory para forzar ProactorEventLoop en Windows. "
            "Esto es necesario porque uvicorn puede ignorar la policy global."
        )
        return asyncio.ProactorEventLoop
    return None


from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from omnivoice_api.settings import get_settings
from omnivoice_api.core.omnivoice_engine import get_engine, close_engine
from omnivoice_api.api.v1 import voices, tts


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verificación defensiva del event loop al arrancar.
    # Si por algún motivo el loop activo no soporta subprocess (p.ej. uvicorn
    # ignoró la policy global), lo detectamos aquí y lo logueamos claramente.
    try:
        current_loop = asyncio.get_running_loop()
        loop_class = type(current_loop).__name__
        is_proactor = isinstance(current_loop, asyncio.ProactorEventLoop)
        is_selector = isinstance(current_loop, asyncio.SelectorEventLoop)
        logger.info(
            "Lifespan startup: loop activo class=%s, is_proactor=%s, is_selector=%s, platform=%s",
            loop_class, is_proactor, is_selector, sys.platform,
        )
        if sys.platform == "win32" and not is_proactor:
            logger.error(
                "ATENCIÓN: en Windows se requiere ProactorEventLoop para asyncio.subprocess, "
                "pero el loop activo es %s. Las llamadas al engine OmniVoice fallarán con "
                "NotImplementedError. Asegúrate de ejecutar con: "
                "uvicorn omnivoice_api.main:app --loop asyncio --loop-factory=proactor "
                "o usa el helper _force_proactor_loop_factory().",
                loop_class,
            )
    except RuntimeError:
        pass

    # Startup
    logger.info("Application startup: inicializando engine OmniVoice...")
    try:
        await get_engine()  # Inicializa el engine (warmup incluido)
        logger.info("Engine OmniVoice inicializado correctamente")
    except Exception as e:
        logger.exception(
            "Fallo durante la inicialización del engine en lifespan.startup: %s",
            e,
        )
        raise
    yield
    # Shutdown
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
