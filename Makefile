# Makefile para OmniVoice API
# Uso: make <target>

.PHONY: help install test lint format run dev clean check-gpu download-model

# Variables
PYTHON := python3
VENV := .venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy
UVICORN := $(VENV)/bin/uvicorn

# Default target
help:
	@echo "OmniVoice API - Comandos disponibles:"
	@echo ""
	@echo "  make install       - Instala dependencias en entorno virtual"
	@echo "  make test          - Ejecuta tests con cobertura"
	@echo "  make lint          - Ejecuta ruff y mypy"
	@echo "  make format        - Formatea código con ruff y black"
	@echo "  make run           - Inicia servidor en producción"
	@echo "  make dev           - Inicia servidor en modo desarrollo (reload)"
	@echo "  make check-gpu     - Verifica disponibilidad de GPU/CUDA"
	@echo "  make download-model - Descarga modelo OmniVoice (placeholder)"
	@echo "  make clean         - Limpia cachés y archivos temporales"
	@echo ""

# Instalación
install: $(VENV)/bin/activate

$(VENV)/bin/activate: pyproject.toml
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
	@mkdir -p models/omnivoice
	@touch models/omnivoice/.gitkeep

clean:
	rm -rf $(VENV)
	rm -rf .mypy_cache .ruff_cache .pytest_cache
	rm -rf storage/outputs/*
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Pre-commit
pre-commit: install
	$(VENV)/bin/pre-commit install
	$(VENV)/bin/pre-commit run --all-files
