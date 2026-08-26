"""Script de verificación de la instalación externa de OmniVoice.

Uso:
    python scripts/check_omnivoice_install.py

Este script:
1. Valida que OMNIVOICE_INSTALL_DIR y OMNIVOICE_VENV_DIR existan.
2. Verifica que el python.exe del venv externo sea accesible.
3. Intenta importar `omnivoice` desde el venv externo para confirmar
   que las dependencias están correctamente instaladas.

Pensado para ser invocado desde el Makefile (target check-omnivoice-install)
de forma portable (Windows + Unix).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Permitir imports del paquete omnivoice_api cuando se ejecuta desde la raíz
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _get_engine_paths() -> tuple[Path, Path] | None:
    """Intenta obtener los paths de instalación desde el módulo core.

    Returns:
        Tupla (install_dir, venv_dir) si el módulo existe, None en caso contrario.
    """
    try:
        from omnivoice_api.core.engine_paths import (  # type: ignore[import-not-found]
            default_install_dir,
            default_venv_dir,
        )
        return default_install_dir(), default_venv_dir()
    except ImportError:
        # El módulo core no existe aún (Sprint 0) - usar fallbacks desde variables de entorno
        return None


def _validate_installation_fallback(install_dir: Path, venv_dir: Path) -> Path:
    """Valida la instalación usando lógica básica sin depender del módulo core."""
    if not install_dir.exists():
        raise FileNotFoundError(f"Directorio de instalación no existe: {install_dir}")
    if not venv_dir.exists():
        raise FileNotFoundError(f"Directorio del venv no existe: {venv_dir}")

    # Buscar python.exe en el venv (Windows) o bin/python (Unix)
    if sys.platform == "win32":
        python_bin = venv_dir / "Scripts" / "python.exe"
    else:
        python_bin = venv_dir / "bin" / "python"

    if not python_bin.exists():
        raise FileNotFoundError(f"Python no encontrado en venv: {python_bin}")

    return python_bin


def main() -> int:
    """Ejecuta las verificaciones. Devuelve 0 si todo OK, 1 si hay error."""
    print("Verificando instalación externa de OmniVoice...")
    print("(1) Validando paths y existencia del venv externo...")

    # Intentar usar el módulo core si existe (Sprint 1+), sino usar fallbacks
    engine_paths = _get_engine_paths()

    if engine_paths:
        install_dir, venv_dir = engine_paths
        try:
            from omnivoice_api.core.engine_paths import validate_installation  # type: ignore[import-not-found]
            python_bin = validate_installation(install_dir, venv_dir)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            print(
                "  Define OMNIVOICE_PATH en .env apuntando al directorio raíz "
                "de la instalación externa."
            )
            return 1
    else:
        # Fallback para Sprint 0: leer desde variables de entorno directamente
        print("  Módulo core no disponible (Sprint 0), usando variables de entorno...")
        omnivoice_path = os.environ.get("OMNIVOICE_PATH")
        if not omnivoice_path:
            print("  ERROR: Variable de entorno OMNIVOICE_PATH no definida")
            print(
                "  Define OMNIVOICE_PATH en .env apuntando al directorio raíz "
                "de la instalación externa de OmniVoice."
            )
            return 1

        install_dir = Path(omnivoice_path)
        venv_dir = install_dir / ".venv"  # Convención estándar

        print(f"  OMNIVOICE_PATH        = {omnivoice_path}")
        print(f"  OMNIVOICE_INSTALL_DIR = {install_dir}")
        print(f"  OMNIVOICE_VENV_DIR    = {venv_dir}")

        try:
            python_bin = _validate_installation_fallback(install_dir, venv_dir)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            return 1

    print(f"  OK: Python del venv externo = {python_bin}")

    print("(2) Verificando que el venv externo tiene las dependencias de OmniVoice...")
    print(f"  Usando Python: {python_bin}")

    check_cmd = (
        "import omnivoice; "
        "print(f'  omnivoice importado OK desde: {omnivoice.__file__}')"
    )
    result = subprocess.run(
        [str(python_bin), "-c", check_cmd],
        capture_output=True,
        text=True,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
