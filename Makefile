# Makefile para OmniVoice API - Compatible con Windows y Unix
# Uso: make <target>

.PHONY: help install test lint format run dev clean check-gpu download-model pre-commit

# Detectar sistema operativo
ifeq ($(OS),Windows_NT)
    # Windows
    PYTHON := python
    VENV := .venv
    PIP := $(VENV)\Scripts\pip.exe
    PYTEST := $(VENV)\Scripts\pytest.exe
    RUFF := $(VENV)\Scripts\ruff.exe
    MYPY := $(VENV)\Scripts\mypy.exe
    UVICORN := $(VENV)\Scripts\uvicorn.exe
    ACTIVATE := $(VENV)\Scripts\activate.bat
    RM_RF := rmdir /s /q
    RM_F := del /f /q
    MKDIR_P := mkdir
    TOUCH := type nul >
    FIND_PYCACHE := for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
    FIND_PYC := del /s /q *.pyc
    NULL := nul
    SHELL := cmd.exe
    .SHELLFLAGS := /c
    # Windows no tiene 'true', usamos 'rem' (no-op) o condicionales
    TRUE_CMD := rem
else
    # Unix/Linux/macOS
    PYTHON := python3
    VENV := .venv
    PIP := $(VENV)/bin/pip
    PYTEST := $(VENV)/bin/pytest
    RUFF := $(VENV)/bin/ruff
    MYPY := $(VENV)/bin/mypy
    UVICORN := $(VENV)/bin/uvicorn
    ACTIVATE := $(VENV)/bin/activate
    RM_RF := rm -rf
    RM_F := rm -f
    MKDIR_P := mkdir -p
    TOUCH := touch
    FIND_PYCACHE := find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    FIND_PYC := find . -type f -name "*.pyc" -delete
    NULL := /dev/null
    SHELL := /bin/bash
    TRUE_CMD := true
endif

# Default target
help:
	@echo "OmniVoice API - Comandos disponibles:"
	@echo ""
	@echo "  make install        - Instala dependencias en entorno virtual"
	@echo "  make test           - Ejecuta tests con cobertura"
	@echo "  make test-unit      - Ejecuta solo tests unitarios"
	@echo "  make test-integration - Ejecuta tests de integración"
	@echo "  make test-load      - Ejecuta tests de carga"
	@echo "  make lint           - Ejecuta ruff y mypy"
	@echo "  make format         - Formatea código con ruff y black"
	@echo "  make run            - Inicia servidor en producción"
	@echo "  make dev            - Inicia servidor en modo desarrollo (reload)"
	@echo "  make check-gpu      - Verifica disponibilidad de GPU/CUDA"
	@echo "  make download-model - Descarga modelo OmniVoice (placeholder)"
	@echo "  make clean          - Limpia cachés y archivos temporales"
	@echo "  make pre-commit     - Instala y ejecuta pre-commit hooks"
	@echo ""

# Instalación
install: $(ACTIVATE)

$(ACTIVATE): pyproject.toml
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"
	@echo "Entorno virtual creado en $(VENV)"

# Tests
test: install
	$(PYTEST) -v

test-unit: install
	$(PYTEST) -v -m "not integration"

test-integration: install
	$(PYTEST) -v -m "integration"

test-load: install
	$(PYTEST) tests/load/ -v --tb=short

# Calidad de código
lint: install
	$(RUFF) check .
	$(MYPY) omnivoice_api

format: install
	$(RUFF) format .
	$(RUFF) check --fix .

# Servidor
run: install
	$(UVICORN) omnivoice_api.main:app --host 0.0.0.0 --port 8000

dev: install
	$(UVICORN) omnivoice_api.main:app --host 0.0.0.0 --port 8000 --reload

# Utilidades
check-gpu: install
	@$(PYTHON) -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda}'); print(f'GPU count: {torch.cuda.device_count()}'); [print(f'  GPU {i}: {torch.cuda.get_device_name(i)}') for i in range(torch.cuda.device_count())]"

download-model: install
	@echo "Descargando modelo OmniVoice..."
	@echo "TODO: Implementar descarga real del modelo desde HuggingFace o fuente oficial"
	@echo "Modelo esperado en: models/omnivoice/"
	$(MKDIR_P) models/omnivoice
	$(TOUCH) models/omnivoice/.gitkeep

# Clean target with OS-specific commands
ifeq ($(OS),Windows_NT)
clean:
	$(RM_RF) $(VENV) 2>$(NULL) || $(TRUE_CMD)
	$(RM_RF) .mypy_cache 2>$(NULL) || $(TRUE_CMD)
	$(RM_RF) .ruff_cache 2>$(NULL) || $(TRUE_CMD)
	$(RM_RF) .pytest_cache 2>$(NULL) || $(TRUE_CMD)
	$(RM_RF) storage\outputs\* 2>$(NULL) || $(TRUE_CMD)
	$(FIND_PYCACHE)
	$(FIND_PYC)
	@echo "Cleanup complete"
else
clean:
	$(RM_RF) $(VENV) 2>$(NULL) || $(TRUE_CMD)
	$(RM_RF) .mypy_cache .ruff_cache .pytest_cache 2>$(NULL) || $(TRUE_CMD)
	$(RM_RF) storage/outputs/* 2>$(NULL) || $(TRUE_CMD)
	$(FIND_PYCACHE)
	$(FIND_PYC)
	@echo "Cleanup complete"
endif

# Pre-commit
pre-commit: install
ifeq ($(OS),Windows_NT)
	$(VENV)\Scripts\pre-commit.exe install
	$(VENV)\Scripts\pre-commit.exe run --all-files
else
	$(VENV)/bin/pre-commit install
	$(VENV)/bin/pre-commit run --all-files
endif
