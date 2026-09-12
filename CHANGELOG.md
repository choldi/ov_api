# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/es/1.1.0/)

## [0.6.0] - 2026-09-12

### Added
- Emociones y singing via `ModelsLab/omnivoice-singing` (drop-in replacement de k2-fsa/OmniVoice)
- Tags de emoción soportados: `happy`, `sad`, `angry`, `excited`, `calm`, `nervous`, `whisper`, `singing`
- Parámetro `emotion` en `POST /api/v1/tts` y `POST /api/v1/tts/instruct`
- Endpoint `GET /api/v1/emotions` — lista emociones soportadas
- Variable de entorno `OMNIVOICE_MODEL_ID` configurable (default: `ModelsLab/omnivoice-singing`)

### Changed
- Modelo por defecto cambiado de `k2-fsa/OmniVoice` a `ModelsLab/omnivoice-singing`
- Documentación de API actualizada (api_spec_simplified.md) con endpoints de emociones y parámetros de generación

## [0.5.0] - 2025-01-XX

### Added
- Streaming WAV por chunks (?stream=true) en TTS y conversaciones
- Guía de despliegue (docs/deployment/)
- Stress tests con locust (tests/load/)

### Changed
- PhasesStatus.md actualizado con estado real de todos los sprints

## [0.4.0] - 2025-01-XX

### Added
- EnginePool con semáforo para concurrencia controlada
- Limpieza automática de outputs caducados (background task)
- Métricas Prometheus (prometheus_fastapi_instrumentator)
- Rate limiting con slowapi
- Logs estructurados con structlog + request_id
- API key opcional (APIKeyMiddleware)
- CORS configurable (CORS_ORIGINS)

## [0.3.0] - 2025-01-XX

### Added
- Endpoint POST /api/v1/conversations para conversaciones multi-voz
- ConversationService con concatenación WAV y silencios
- Tests de integración para conversaciones

## [0.2.0] - 2025-01-XX

### Added
- Voice cloning: POST /api/v1/voices/clone
- Voice CRUD: GET/DELETE /api/v1/voices/cloned/{id}
- VoiceService con validación de audio
- SQLite para persistencia de voces clonadas
- core/audio.py con validación y normalización
- GenerationParams para control fino de síntesis
- Voice design tokens endpoint
- Instruct API para voice design libre
- Clone + instruct combo

### Removed
- Emociones (Sprint 4) — removidas por diseño, integradas en engine

## [0.1.0] - 2025-01-XX

### Added
- MVP: TTS con voces stock
- GET /api/v1/voices/stock
- POST /api/v1/tts
- OmniVoiceEngine con fallback a mock
- Health endpoints (/health, /health/live, /health/ready)
- Tests unitarios e integración
- Dockerfile
