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
    OMNIVOICE_LANGUAGES: str = "es,en,zh,ja,ko,fr,de"
    MAX_REFERENCE_DURATION_SEC: int = 30
    ENGINE_CONCURRENCY: int = 1
    ENGINE_REQUEST_TIMEOUT_SEC: int = 120

    # --- Mock / Real engine toggle ---
    # Si True, usa generación de tonos mock (útil para tests sin GPU/modelo).
    # Si False (por defecto), llama al motor OmniVoice real vía subprocess.
    OMNIVOICE_USE_MOCK: bool = False

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
    def omnilang_list(self) -> list[str]:
        """Lista de idiomas como lista de strings."""
        return [lang.strip() for lang in self.OMNIVOICE_LANGUAGES.split(",") if lang.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        """Lista de orígenes CORS como lista de strings."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def model_path(self) -> Path:
        """Ruta resuelta al modelo (derivada de OMNIVOICE_MODEL_ID via HuggingFace)."""
        return self.OMNIVOICE_MODEL_ID


def get_settings() -> Settings:
    """Obtener una nueva instancia de configuración que lee las variables de entorno actuales."""
    return Settings()
