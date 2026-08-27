from pydantic import BaseSettings
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    APP_NAME: str
    OMNIVOICE_INSTALL_DIR: str
    OMNIVOICE_VENV_DIR: str
    OMNIVOICE_PATH: str
    # ... otras variables según tu configuración
