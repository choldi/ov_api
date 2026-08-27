"""Configuración de la aplicación usando pydantic-settings.

OmniVoice NO se instala como dependencia de este proyecto. Se consume desde
una instalación externa (ver ``docs/INSTALLATION.md``).
"""

from __future__ import annotations

import json
import os
import warnings
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from omnivoice_api.core.engine_paths import (
    default_install_dir,
    default_venv_dir,
    python_bin_from_venv,
)


def _resolve_env_file() -> tuple[str | None, str | None]:
    """
    Resuelve qué archivo .env usar.

    Returns:
        Tupla (env_file_path, warning_message).
        - env_file_path: ruta al archivo a usar (None si no existe ninguno)
        - warning_message: mensaje de advertencia si ambos existen, None en caso contrario
    """
    cwd = Path.cwd()
    dot_env = cwd / ".env"
    env_file = cwd / "env"

    dot_exists = dot_env.exists()
    env_exists = env_file.exists()

    if dot_exists and env_exists:
        # Prioridad a .env, pero avisar
        warning = (
            f"Se detectaron ambos archivos: {dot_env} y {env_file}. "
            f"Se usará {dot_env} (prioridad .env sobre env)."
        )
        return str(dot_env), warning
    elif dot_exists:
        return str(dot_env), None
    elif env_exists:
        return str(env_file), None
    else:
        # No existe ninguno, pydantic-settings usará el default (.env) pero no fallará
        return ".env", None


# Resolver el archivo de entorno al importar el módulo
_ENV_FILE_PATH, _ENV_WARNING = _resolve_env_file()


class Settings(BaseSettings):
    """Configuración global de OmniVoice API."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE_PATH,
        env_file_encoding="utf-8",
        env_prefix="OMNIVOICE_",
        case_sensitive=False,
        extra="ignore",
    )

    # Campo para exponer qué archivo .env se está usando
    ENV_FILE_USED: str = Field(
        default=_ENV_FILE_PATH or "none",
        description="Ruta del archivo .env utilizado para la configuración",
        validation_alias="ENV_FILE_USED",
    )

    # --- App ---
    APP_NAME: str = Field(default="OmniVoice API", validation_alias="APP_NAME")
    APP_VERSION: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    DEBUG: bool = Field(default=True, validation_alias="DEBUG")  # True para desarrollo
    API_PREFIX: str = Field(default="/api/v1", validation_alias="API_PREFIX")

    # --- OmniVoice Engine (instalación externa) ---
    OMNIVOICE_INSTALL_DIR: Path = Field(
        default_factory=default_install_dir,
        description="Directorio de la instalación externa de OmniVoice",
        validation_alias="INSTALL_DIR",
    )
    # Alias aceptado por scripts externos (ej. check-omnivoice-install).
    OMNIVOICE_PATH: Path | None = Field(
        default=None,
        description="Alias de INSTALL_DIR (compatibilidad con scripts)",
        validation_alias="PATH",
    )
    OMNIVOICE_VENV_DIR: Path = Field(
        default_factory=default_venv_dir,
        description="Directorio del venv externo que contiene OmniVoice + CUDA",
        validation_alias="VENV_DIR",
    )
    OMNIVOICE_PYTHON_BIN: Path | None = Field(
        default=None,
        description="Ruta al python.exe del venv externo (derivada)",
        validation_alias="PYTHON_BIN",
    )
    OMNIVOICE_CLI_ENTRY: str = Field(
        default="omnivoice_cli.__main__",
        description="Módulo CLI ejecutable dentro del venv externo",
        validation_alias="CLI_ENTRY",
    )
    OMNIVOICE_MODEL_PATH: Path | None = Field(
        default=None,
        description="Ruta al modelo (por defecto, dentro de INSTALL_DIR)",
        validation_alias="MODEL_PATH",
    )
    OMNIVOICE_DEVICE: str = Field(
        default="cuda:0",
        description="Dispositivo de inferencia (lo gestiona el venv externo)",
        validation_alias="DEVICE",
    )
    OMNIVOICE_LANGUAGES: list[str] = Field(
        default=["es", "en", "zh", "ja", "ko", "fr", "de"],
        description="Lista de códigos de idioma ISO 639-1 soportados",
        validation_alias="LANGUAGES",
    )
    MAX_REFERENCE_DURATION_SEC: int = Field(
        default=30,
        description="Duración máxima permitida para audio de referencia (segundos)",
        validation_alias="MAX_REFERENCE_DURATION_SEC",
    )
    ENGINE_CONCURRENCY: int = Field(
        default=1,
        description="Número máximo de síntesis simultáneas (P2000 = 1)",
        validation_alias="ENGINE_CONCURRENCY",
    )
    ENGINE_STARTUP_TIMEOUT_SEC: int = Field(
        default=30,
        description="Timeout para el arranque del subprocess del engine",
        validation_alias="ENGINE_STARTUP_TIMEOUT_SEC",
    )
    ENGINE_REQUEST_TIMEOUT_SEC: int = Field(
        default=120,
        description="Timeout por petición al engine",
        validation_alias="ENGINE_REQUEST_TIMEOUT_SEC",
    )

    # --- Storage ---
    STORAGE_BASE_PATH: Path = Field(
        default=Path("storage"),
        description="Directorio base para almacenamiento",
        validation_alias="STORAGE_BASE_PATH",
    )
    VOICES_DIR: Path = Field(
        default=Path("storage/voices"),
        description="Directorio para voces clonadas",
        validation_alias="VOICES_DIR",
    )
    OUTPUTS_DIR: Path = Field(
        default=Path("storage/outputs"),
        description="Directorio para outputs temporales",
        validation_alias="OUTPUTS_DIR",
    )
    CACHE_DIR: Path = Field(
        default=Path("storage/cache"),
        description="Directorio para caché de embeddings",
        validation_alias="CACHE_DIR",
    )
    OUTPUT_TTL_SECONDS: int = Field(
        default=3600,
        description="TTL para archivos de output temporales (segundos)",
        validation_alias="OUTPUT_TTL_SECONDS",
    )

    # --- Database ---
    DATABASE_URL: str = Field(
        default="sqlite:///storage/omnivoice.db",
        description="URL de conexión a la base de datos",
        validation_alias="DATABASE_URL",
    )

    # --- Security ---
    API_KEY: str | None = Field(
        default=None,
        description="API Key opcional para proteger endpoints (None = desactivado)",
        validation_alias="API_KEY",
    )
    CORS_ORIGINS: str | list[str] = Field(
        default=["*"],
        description="Orígenes permitidos para CORS",
        validation_alias="CORS_ORIGINS",
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=10,
        description="Tamaño máximo de upload en MB",
        validation_alias="MAX_UPLOAD_SIZE_MB",
    )

    # --- Observability ---
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Nivel de logging (DEBUG, INFO, WARNING, ERROR)",
        validation_alias="LOG_LEVEL",
    )
    LOG_FORMAT: str = Field(
        default="json",
        description="Formato de logs: json o console",
        validation_alias="LOG_FORMAT",
    )

    @model_validator(mode="after")
    def _resolve_paths(self) -> Settings:
        """Resuelve paths derivados y valida existencia solo en producción."""
        # Mostrar advertencia si ambos archivos .env y env existen
        if _ENV_WARNING:
            warnings.warn(_ENV_WARNING, UserWarning, stacklevel=2)
            # También imprimir a stderr para visibilidad inmediata en consola
            print(f"[CONFIG WARNING] {_ENV_WARNING}", file=os.sys.stderr)

        # Log del archivo .env usado (solo en DEBUG)
        if self.DEBUG:
            print(f"[CONFIG] Usando archivo de entorno: {self.ENV_FILE_USED}", file=os.sys.stderr)

        # Sincronizar OMNIVOICE_PATH con INSTALL_DIR si no se proporcionó explícitamente
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

        # Validar paths críticos SOLO en producción (DEBUG=False)
        # En desarrollo (DEBUG=True) permitimos arrancar sin instalación externa
        # para facilitar tests y desarrollo con engine mockeado.
        if not self.DEBUG:
            if not self.OMNIVOICE_INSTALL_DIR.exists():
                raise ValueError(
                    f"OMNIVOICE_INSTALL_DIR no existe: {self.OMNIVOICE_INSTALL_DIR}. "
                    "Define OMNIVOICE_INSTALL_DIR y OMNIVOICE_VENV_DIR en .env "
                    "o OMNIVOICE_PATH apuntando a la instalación externa de OmniVoice. "
                    "Ver docs/INSTALLATION.md"
                )
            if not self.OMNIVOICE_VENV_DIR.exists():
                raise ValueError(
                    f"OMNIVOICE_VENV_DIR no existe: {self.OMNIVOICE_VENV_DIR}. "
                    "Define OMNIVOICE_VENV_DIR en .env o asegúrate de que el venv "
                    "esté en OMNIVOICE_INSTALL_DIR/.venv"
                )

        # Crear directorios locales (siempre, tanto en dev como prod)
        self.VOICES_DIR.mkdir(parents=True, exist_ok=True)
        self.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Convertir CORS_ORIGINS si es una cadena
        if isinstance(self.CORS_ORIGINS, str):
            s = self.CORS_ORIGINS.strip()
            if s == "":
                cors_origins = []
            elif s == "*":
                cors_origins = ["*"]
            else:
                # Intentar parsear como JSON
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        # Validar que todos los elementos sean strings
                        if all(isinstance(item, str) for item in parsed):
                            cors_origins = parsed
                        else:
                            # Volver a dividir por comas si no es una lista de strings
                            cors_origins = [part.strip() for part in s.split(",")]
                    else:
                        # Si no es una lista, dividir por comas
                        cors_origins = [part.strip() for part in s.split(",")]
                except json.JSONDecodeError:
                    # No es JSON válido, dividir por comas
                    cors_origins = [part.strip() for part in s.split(",")]
            object.__setattr__(self, "CORS_ORIGINS", cors_origins)

        return self


@lru_cache
def get_settings() -> Settings:
    """Devuelve la instancia de settings (cached)."""
    return Settings()


settings = get_settings()
