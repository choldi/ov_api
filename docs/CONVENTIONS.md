# CONVENTIONS.md

## 1. Stack tecnológico

- Python: 3.11+
- Framework HTTP: FastAPI + Uvicorn (asyncio)
- TTS Engine: OmniVoice (k2-fsa) sobre PyTorch + CUDA (NVIDIA P2000, 5 GB VRAM)
- Validación: Pydantic v2
- Persistencia: SQLite (metadatos) + filesystem (audio). Reservado slot para migrar a Postgres.
- Testing: pytest + pytest-asyncio + httpx (AsyncClient) + pytest-cov
- Calidad: ruff (lint+format), mypy (strict en src/)
- Empaquetado: Poetry o uv + pyproject.toml

## 2. Estilo de código

- black con line-length = 100
- isort con perfil black
- ruff con reglas: E, F, I, B, UP, SIM, RET, PL
- Tipado estático obligatorio en toda función pública
- Docstrings estilo Google en módulos, clases y funciones públicas
- Nomenclatura:
  - PascalCase clases, snake_case funciones/variables, UPPER_SNAKE constantes
  - Enums en SCREAMING_SNAKE
  - Endpoints en kebab-case: /api/v1/voices/cloned

## 3. Estructura por capas

api → services → repositories → core(engine) → models

- La capa api no importa omnivoice directamente.
- La capa core es la única que sabe hablar con el engine OmniVoice.
- services orquesta casos de uso, no conoce HTTP.
- repositories abstrae persistencia (fácil de cambiar SQLite → Postgres).

## 4. Reglas para la API REST

- Prefijo /api/v1
- Versionado por path
- Verbos HTTP semánticos: GET/POST/DELETE (PUT sólo para replace completo, PATCH para parcial)
- Paginación: ?limit=20&offset=0
- Errores con formato RFC 7807 (application/problem+json)
- Códigos: 200, 201, 204, 400, 404, 409, 422, 500
- Streaming de audio vía StreamingResponse con media_type="audio/wav" o "audio/mpeg"
- IDs públicos en UUIDv4 (no exponer PK de BD)

## 5. Manejo de errores

- Toda excepción de dominio hereda de OmniVoiceAPIError (en core/exceptions.py)
- Conversión centralizada en un handler de FastAPI
- Nunca filtrar trazas al cliente; log interno con structlog

## 6. Configuración

- Toda config via Settings (pydantic-settings) cargada desde .env
- Nunca hardcoded secrets
- Validar al arranque (VRAM mínima, paths existentes, modelo descargado)

## 7. Async / sync

- Endpoints async def
- El engine OmniVoice es síncrono y bloqueante → envolver llamadas con run_in_threadpool o asyncio.to_thread
- Un único EnginePool con asyncio.Semaphore(1) en P2000 (evitar OOM)

## 8. Testing

- Cobertura mínima: 80% en src/
- Tests unitarios: lógica de servicios con engine mockeado
- Tests de integración: API end-to-end con fixtures de audio
- Fixtures en tests/conftest.py
- Patrón AAA (Arrange, Act, Assert)
- Nombres: test_<unit>_<scenario>_<expected>
- Mock del engine vía protocol/ABC OmniVoiceEngineInterface

## 9. Git / Commits

- Conventional Commits: feat:, fix:, docs:, test:, refactor:, chore:, perf:
- Una feature = un commit atómico (o squash semántico)
- Branches: feat/<sprint>-<slug>, fix/<slug>, docs/<slug>
- PRs pequeños (<400 líneas diff)

## 10. Documentación

- Cada endpoint con summary, description, response_model, responses
- Ejemplos en OpenAPI vía examples= de Pydantic
- README siempre actualizado con quickstart
- Diagramas en docs/ (Mermaid)

## 11. Convenciones de audio

- Sample rate interno: 22050 Hz (estándar OmniVoice)
- Formato de salida por defecto: WAV (PCM 16-bit)
- Conversión a MP3 opcional vía lameenc
- Audio de referencia para clonado: 5-30 s, mono, 22050 Hz, sin ruido de fondo

## 12. Reglas especiales para aider

- Antes de proponer cambios, leer siempre PHASES.md y ubicar la fase activa
- Nunca generar código sin tests asociados
- Cada prompt a aider debe referenciar: [Fase X] <tarea>
- Si una tarea excede 1 archivo → partir en subtareas
- Tras cada cambio: make test (o pytest -q) debe pasar en verde
- Mantén el fichero PhasesStatus.md marcando las fases completadas con [x]


