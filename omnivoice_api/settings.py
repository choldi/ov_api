"""Configuración de la aplicación usando pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # --- OmniVoice Engine ---
    OMNIVOICE_MODEL_PATH: Path = Field(
        default=Path("models/omnivoice"),
        description="Ruta al directorio del modelo OmniVoice (k2-fsa)",
    )
    OMNIVOICE_DEVICE: str = Field(
        default="cuda:0",
        description="Dispositivo para inferencia (cuda:0, cpu, etc.)",
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Asegurar que los directorios existan
        self.VOICES_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.OMNIVOICE_MODEL_PATH.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Devuelve la instancia de settings (cached)."""
    return Settings()


settings = get_settings()
