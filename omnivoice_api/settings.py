from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal
from pathlib import Path
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    APP_NAME: str = "OmniVoice API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    # --- OmniVoice Engine ---
    OMNIVOICE_MODEL_ID: str = "k2-fsa/OmniVoice"
    OMNIVOICE_DTYPE: Literal["float16", "float32", "int8"] = "float16"
    OMNIVOICE_WARMUP_ON_START: bool = False
    OMNIVOICE_DEVICE: str = "cuda:0"

    # --- Mock / Real engine toggle ---
    # Si True, usa generación de tonos mock (útil para tests sin GPU/modelo).
    # Si False (por defecto), usa el motor OmniVoice real.
    OMNIVOICE_USE_MOCK: bool = False
    # Si True, cuando el motor real falle al arrancar, la API cae
    # automáticamente al modo mock en lugar de crashear. El endpoint
    # /api/v1/health devolverá status="degraded" y el campo
    # real_engine_error con la causa raíz.
    OMNIVOICE_FALLBACK_TO_MOCK: bool = True

    # --- Database ---
    DATABASE_URL: str = "sqlite:///storage/omnivoice.db"

    # --- Storage ---
    STORAGE_BASE_PATH: Path = Path("storage")
    VOICES_DIR: Path = Path("storage/voices")
    OUTPUTS_DIR: Path = Path("storage/outputs")
    CACHE_DIR: Path = Path("storage/cache")
    OUTPUT_TTL_SECONDS: int = 3600

    # --- Security ---
    API_KEY: str = ""
    CORS_ORIGINS: str = "*"
    MAX_UPLOAD_SIZE_MB: int = 10

    # --- Observability ---
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"

    @property
    def cors_origins_list(self) -> list[str]:
        """Lista de orígenes CORS como lista de strings."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


def get_settings() -> Settings:
    """Obtener una nueva instancia de configuración que lee las variables de entorno actuales."""
    return Settings()
