print("[DEBUG] Importing settings.py - VERSION 2", flush=True)
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
    OMNIVOICE_INSTALL_DIR: Path
    OMNIVOICE_VENV_DIR: Path
    OMNIVOICE_PATH: Path
    OMNIVOICE_MODEL_PATH: Path | None = None
    OMNIVOICE_CLI_ENTRY: str = "omnivoice_cli.__main__"
    OMNIVOICE_DEVICE: str = "cuda:0"
    OMNIVOICE_LANGUAGES: str = "es,en,zh,ja,ko,fr,de"
    MAX_REFERENCE_DURATION_SEC: int = 30
    ENGINE_CONCURRENCY: int = 1
    ENGINE_STARTUP_TIMEOUT_SEC: int = 30
    ENGINE_REQUEST_TIMEOUT_SEC: int = 120

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
        """Ruta resuelta al modelo (usa OMNIVOICE_MODEL_PATH o deriva de INSTALL_DIR)."""
        if self.OMNIVOICE_MODEL_PATH:
            return self.OMNIVOICE_MODEL_PATH
        return self.OMNIVOICE_INSTALL_DIR / "models"

    @property
    def python_bin(self) -> Path:
        """Ruta al python del venv externo de OmniVoice."""
        if os.name == "nt":
            return self.OMNIVOICE_VENV_DIR / "Scripts" / "python.exe"
        return self.OMNIVOICE_VENV_DIR / "bin" / "python"


def get_settings() -> Settings:
    """Obtener una nueva instancia de configuración que lee las variables de entorno actuales."""
    settings = Settings()
    print(f"[DEBUG] Creating Settings instance:")
    print(f"[DEBUG]   OMNIVOICE_INSTALL_DIR: {settings.OMNIVOICE_INSTALL_DIR}")
    print(f"[DEBUG]   OMNIVOICE_VENV_DIR: {settings.OMNIVOICE_VENV_DIR}")
    print(f"[DEBUG]   model_path: {settings.model_path}")
    print(f"[DEBUG]   python_bin: {settings.python_bin}")
    return settings
