from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Literal
from pathlib import Path


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
    OMNIVOICE_LANGUAGES: list[str] = Field(default_factory=lambda: ["es", "en", "zh", "ja", "ko", "fr", "de"])
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
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["*"])
    MAX_UPLOAD_SIZE_MB: int = 10

    # --- Observability ---
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_FORMAT: Literal["json", "console"] = "json"

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


_settings_instance: Settings | None = None


def get_settings() -> Settings:
    """Singleton para obtener la configuración (cacheada)."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
