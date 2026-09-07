"""Script de verificación de la instalación de OmniVoice.

Uso:
    python scripts/check_omnivoice_install.py

Este script:
1. Verifica que el venv actual (el de omnivoice_api) puede importar omnivoice.
   Esto es lo que ocurre tras `make install`, que instala OmniVoice desde git
   en el mismo entorno que la API.
2. Si falla, valida una instalación externa alternativa con rutas de .env
   (OMNIVOICE_INSTALL_DIR / OMNIVOICE_VENV_DIR o OMNIVOICE_PATH).
3. Verifica que el python del venv externo pueda importar omnivoice.

Pensado para ser invocado desde el Makefile (target check-omnivoice-install)
de forma portable (Windows + Unix).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def check_current_venv_import() -> bool:
    """Verifica que el venv actual puede importar omnivoice.

    Es el caso esperado tras `make install`, que ejecuta:
        pip install git+https://github.com/k2-fsa/OmniVoice.git
    en el mismo entorno virtual que omnivoice_api.
    """
    print("(1) Verificando instalación en el venv actual (make install)...")
    try:
        import omnivoice  # noqa: PLC0415

        print(f"  OK: omnivoice importado desde: {omnivoice.__file__}")
        return True
    except ImportError:
        print("  No se encontró omnivoice en el venv actual")
        return False


def check_external_install() -> bool:
    """Verifica instalación externa usando rutas de .env."""
    print("(2) Verificando instalación externa (fallback)...")

    # Permitir imports del paquete omnivoice_api
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    # Cargar .env para obtener rutas externas
    from omnivoice_api.core.engine_paths import load_env_file  # noqa: E402

    load_env_file()

    from omnivoice_api.core.engine_paths import (  # noqa: E402
        default_install_dir,
        default_venv_dir,
        python_bin_from_venv,
        validate_installation,
    )

    install_dir = default_install_dir()
    venv_dir = default_venv_dir()

    print(f"  OMNIVOICE_INSTALL_DIR = {install_dir}")
    print(f"  OMNIVOICE_VENV_DIR    = {venv_dir}")

    try:
        python_bin = validate_installation(install_dir, venv_dir)
    except Exception as exc:
        print(f"  ERROR: {exc}")
        print(
            "  Define OMNIVOICE_INSTALL_DIR y OMNIVOICE_VENV_DIR en .env "
            "o OMNIVOICE_PATH apuntando a la instalación externa."
        )
        return False

    print(f"  OK: Python del venv externo = {python_bin}")

    # Verificar que el venv externo puede importar omnivoice
    check_cmd = (
        "import omnivoice; "
        "print(f'  omnivoice importado OK desde: {omnivoice.__file__}')"
    )
    result = subprocess.run(
        [str(python_bin), "-c", check_cmd],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return result.returncode == 0


def main() -> int:
    """Ejecuta las verificaciones. Devuelve 0 si todo OK, 1 si hay error."""
    print("Verificando instalación de OmniVoice...")

    # Primero verificar el venv actual (camino principal tras `make install`)
    if check_current_venv_import():
        print("\nOmniVoice verificado correctamente (instalación en el venv actual)")
        return 0

    # Si falla, intentar con instalación externa como fallback
    if check_external_install():
        print("\nOmniVoice verificado correctamente (instalación externa)")
        return 0

    print("\nERROR: No se encontró instalación de OmniVoice")
    print("Opciones:")
    print("  1. Ejecuta `make install` (instala OmniVoice desde git en el venv actual)")
    print("  2. Define rutas externas en .env (OMNIVOICE_INSTALL_DIR, OMNIVOICE_VENV_DIR)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
