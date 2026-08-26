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

    def model_post_init(self, __context: object) -> None:
        """Deriva rutas y crea directorios locales."""
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
        # Crear directorios locales
        self.VOICES_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Devuelve la instancia de settings (cached)."""
    return Settings()


settings = get_settings()
