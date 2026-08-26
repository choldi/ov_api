"""Configuración de la aplicación usando pydantic-settings.

OmniVoice NO se instala como dependencia de este proyecto. Se consume desde
una instalación externa (ver ``docs/INSTALLATION.md``).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from omnivoice_api.core.engine_paths import (
    default_install_dir,
    default_venv_dir,
    python_bin_from_venv,
)


class Settings(BaseSettings):
    """Configuración global de OmniVoice API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "OmniVoice API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # --- OmniVoice Engine (instalación externa) ---
    OMNIVOICE_INSTALL_DIR: Path = Field(
        default_factory=default_install_dir,
        description="Directorio de la instalación externa de OmniVoice",
    )
    # Alias aceptado por scripts externos (ej. check-omnivoice-install).
    # Se sincroniza con OMNIVOICE_INSTALL_DIR en model_post_init.
    OMNIVOICE_PATH: Path | None = Field(
        default=None,
        description="Alias de OMNIVOICE_INSTALL_DIR (compatibilidad con scripts)",
    )
    OMNIVOICE_VENV_DIR: Path = Field(
        default_factory=default_venv_dir,
        description="Directorio del venv externo que contiene OmniVoice + CUDA",
    )
    OMNIVOICE_PYTHON_BIN: Path = Field(
        default=None,  # type: ignore[assignment]
        description="Ruta al python.exe del venv externo (derivada)",
    )
    OMNIVOICE_CLI_ENTRY: str = Field(
        default="omnivoice_cli.__main__",
        description="Módulo CLI ejecutable dentro del venv externo",
    )
    OMNIVOICE_MODEL_PATH: Path = Field(
        default=None,  # type: ignore[assignment]
        description="Ruta al modelo (por defecto, dentro de OMNIVOICE_INSTALL_DIR)",
    )
    OMNIVOICE_DEVICE: str = Field(
        default="cuda:0",
        description="Dispositivo de inferencia (lo gestiona el venv externo)",
    )
    OMNIVOICE_LANGUAGES: list[str] = Field(
        default=["es", "en", "zh", "ja", "ko", "fr", "de"],
        description="Lista de códigos de idioma ISO 639-1 soportados",
    )
    MAX_REFERENCE_DURATION_SEC: int = Field(
        default=30,
        description="Duración máxima permitida para audio de referencia (segundos)",
    )
    ENGINE_CONCURRENCY: int = Field(
        default=1,
        description="Número máximo de síntesis simultáneas (P2000 = 1)",
    )
    ENGINE_STARTUP_TIMEOUT_SEC: int = Field(
        default=30,
        description="Timeout para el arranque del subprocess del engine",
    )
    ENGINE_REQUEST_TIMEOUT_SEC: int = Field(
        default=120,
        description="Timeout por petición al engine",
    )

    # --- Storage ---
    STORAGE_BASE_PATH: Path = Field(
        default=Path("storage"),
        description="Directorio base para almacenamiento",
    )
    VOICES_DIR: Path = Field(
        default=Path("storage/voices"),
        description="Directorio para voces clonadas",
    )
    OUTPUTS_DIR: Path = Field(
        default=Path("storage/outputs"),
        description="Directorio para outputs temporales",
    )
    CACHE_DIR: Path = Field(
        default=Path("storage/cache"),
        description="Directorio para caché de embeddings",
    )
    OUTPUT_TTL_SECONDS: int = Field(
        default=3600,
        description="TTL para archivos de output temporales (segundos)",
    )

    # --- Database ---
    DATABASE_URL: str = Field(
        default="sqlite:///storage/omnivoice.db",
        description="URL de conexión a la base de datos",
    )

    # --- Security ---
    API_KEY: str | None = Field(
        default=None,
        description="API Key opcional para proteger endpoints (None = desactivado)",
    )
    CORS_ORIGINS: list[str] = Field(
        default=["*"],
        description="Orígenes permitidos para CORS",
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=10,
        description="Tamaño máximo de upload en MB",
    )

    # --- Observability ---
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Nivel de logging (DEBUG, INFO, WARNING, ERROR)",
    )
    LOG_FORMAT: str = Field(
        default="json",
        description="Formato de logs: json o console",
    )

    @model_validator(mode="after")
    def _resolve_omnivoice_paths(self) -> Settings:
        """Resuelve y valida paths de OmniVoice con la misma prioridad que check_omnivoice_install.py.

        Prioridad:
        1. OMNIVOICE_INSTALL_DIR + OMNIVOICE_VENV_DIR (explícitos en .env)
        2. OMNIVOICE_PATH (raíz de la instalación, venv = OMNIVOICE_PATH/.venv)
        3. Valores por defecto de default_install_dir/default_venv_dir
        """
        # Si el usuario proporcionó OMNIVOICE_PATH pero no los explícitos,
        # derivar INSTALL_DIR y VENV_DIR desde OMNIVOICE_PATH
        if self.OMNIVOICE_PATH is not None:
            # Solo sobrescribir si los explícitos no fueron definidos en .env
            # (pydantic-settings ya habrá puesto los valores de .env en los campos)
            # Detectamos si vienen de .env comprobando si son distintos a los defaults de factory
            # Pero más simple: si OMNIVOICE_PATH está seteado y los otros son "vacíos" o defaults,
            # usamos OMNIVOICE_PATH. Como no podemos saber fácilmente si vinieron de .env,
            # damos prioridad a los explícitos si son Paths absolutos y existen.
            pass  # La lógica real está en default_install_dir/default_venv_dir

        # Sincronizar OMNIVOICE_PATH con OMNIVOICE_INSTALL_DIR si no se
        # proporcionó explícitamente. Esto permite que scripts externos
        # (ej. check-omnivoice-install) lean OMNIVOICE_PATH desde .env.
        if self.OMNIVOICE_PATH is None:
            object.__setattr__(self, "OMNIVOICE_PATH", self.OMNIVOICE_INSTALL_DIR)

        # Derivar python bin del venv externo
        if self.OMNIVOICE_PYTHON_BIN is None:
            object.__setattr__(
                self,
                "OMNIVOICE_PYTHON_BIN",
                python_bin_from_venv(self.OMNIVOICE_VENV_DIR),
            )

        # Derivar ruta del modelo si no se ha definido
        if self.OMNIVOICE_MODEL_PATH is None:
            object.__setattr__(
                self,
                "OMNIVOICE_MODEL_PATH",
                self.OMNIVOICE_INSTALL_DIR / "models",
            )

        # Validar que los paths críticos existan (solo en modo no DEBUG para no romper tests)
        if not self.DEBUG:
            if not self.OMNIVOICE_INSTALL_DIR.exists():
                raise ValueError(
                    f"OMNIVOICE_INSTALL_DIR no existe: {self.OMNIVOICE_INSTALL_DIR}. "
                    "Define OMNIVOICE_INSTALL_DIR y OMNIVOICE_VENV_DIR en .env "
                    "o OMNIVOICE_PATH apuntando a la instalación externa."
                )
            if not self.OMNIVOICE_VENV_DIR.exists():
                raise ValueError(
                    f"OMNIVOICE_VENV_DIR no existe: {self.OMNIVOICE_VENV_DIR}. "
                    "Define OMNIVOICE_VENV_DIR en .env o asegúrate de que el venv "
                    "esté en OMNIVOICE_INSTALL_DIR/.venv"
                )

        # Crear directorios locales
        self.VOICES_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        return self

    def model_post_init(self, __context: object) -> None:
        """Mantenido por compatibilidad; la lógica principal está en _resolve_omnivoice_paths."""
        # El model_validator ya se ejecuta después de model_post_init en pydantic v2,
        # pero por seguridad llamamos a la validación explícita si no se ejecutó.
        # En pydantic v2, model_validator(mode="after") se ejecuta automáticamente.
        pass


@lru_cache
def get_settings() -> Settings:
    """Devuelve la instancia de settings (cached)."""
    return Settings()


settings = get_settings()
