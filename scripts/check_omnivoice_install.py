
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

from omnivoice_api.core.engine_paths import (  # noqa: E402
    default_install_dir,
    default_venv_dir,
    validate_installation,
)


def main() -> int:
    """Ejecuta las verificaciones. Devuelve 0 si todo OK, 1 si hay error."""
    print("Verificando instalación externa de OmniVoice...")
    print("(1) Validando paths y existencia del venv externo...")

    install_dir = default_install_dir()
    venv_dir = default_venv_dir()

    print(f"  OMNIVOICE_PATH        = {os.environ.get('OMNIVOICE_PATH', '<no definido>')}")
    print(f"  OMNIVOICE_INSTALL_DIR = {install_dir}")
    print(f"  OMNIVOICE_VENV_DIR    = {venv_dir}")

    try:
        python_bin = validate_installation(install_dir, venv_dir)
    except Exception as exc:
        print(f"  ERROR: {exc}")
        print(
            "  Define OMNIVOICE_PATH en .env apuntando al directorio raíz "
            "de la instalación externa."
        )
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

