
---

### 3. Archivo: PHASES.md

```text
# Fases de desarrollo (Scrum-like)

Cada fase = Sprint. MVP al final de la Fase 1. Cada fase incluye tests + ejemplos.

Convención para aider: comienza cada prompt con [Fase N].

---

## Sprint 0 — Setup (1 día)

Objetivo: entorno reproducible y arrancable.

Tareas
- [ ] Crear pyproject.toml con dependencias pinned
- [ ] settings.py con pydantic-settings
- [ ] main.py mínimo con /health
- [ ] conftest.py base + fixture de cliente async
- [ ] Makefile/tasks.py con make test, make lint, make run
- [ ] Validar GPU detectada por PyTorch (torch.cuda.is_available())
- [ ] README con quickstart

Definition of Done
- pytest pasa con 1 test smoke
- uvicorn levanta y /api/v1/health responde {"status":"ok","gpu":true}

---

## Sprint 1 — MVP: TTS con voz stock (2 días) 🎯 MVP

Objetivo: generar audio desde texto con voces predefinidas.

Endpoints
- GET /api/v1/voices/stock → lista {voice_id, language, gender, name}
- POST /api/v1/tts → body {text, voice_id, language, speed?} → audio/wav

Tareas
- [ ] OmniVoiceEngineInterface (Protocol)
- [ ] OmniVoiceEngine concreto (singleton, warm-up)
- [ ] TtsService.synthesize_stock(...)
- [ ] Router tts.py + voices.py (sólo stock)
- [ ] Manejo de UnsupportedLanguage, VoiceNotFound
- [ ] Tests unitarios del servicio (engine mockeado)
- [ ] Tests de integración con audio real generado
- [ ] Ejemplo en docs/examples/curl_tts_stock.sh

DoD
- curl -X POST .../api/v1/tts -d '{"text":"hola","voice_id":"es-mx-male","language":"es"}' devuelve WAV válido
- Cobertura ≥ 80% en services/ y api/

---

## Sprint 2 — Clonado de voces (3 días)

Objetivo: alta/baja/listado/uso de voces clonadas.

Endpoints
- POST /api/v1/voices/clone (multipart: reference + name + language)
- GET /api/v1/voices/cloned?limit=&offset=
- GET /api/v1/voices/cloned/{id}
- DELETE /api/v1/voices/cloned/{id}
- POST /api/v1/tts extiende body con voice_id que apunte a voz clonada

Tareas
- [ ] SQLite + migración inicial (alembic o sql-file)
- [ ] VoiceRepository CRUD
- [ ] VoiceService.clone(): validar duración/sr/mono, normalizar, almacenar
- [ ] core/audio.py: validación con soundfile, conversión a 22050 mono
- [ ] Caché de embeddings (LRU)
- [ ] Tests con audio fixture (tests/fixtures/ref.wav)
- [ ] Ejemplo Python docs/examples/clone_voice.py

DoD
- Clonar, listar, usar, borrar → flujo completo verde en tests de integración
- Audio de referencia inválido → 422 con problema RFC 7807

---

## Sprint 3 — Conversaciones multi-voz (2 días)

Objetivo: generar diálogo entre 2 voces con turnos.

Endpoints
- POST /api/v1/conversations → body:
  {
    "turns": [
      {"voice_id":"...","text":"Hola, ¿cómo estás?"},
      {"voice_id":"...","text":"Muy bien, gracias"}
    ],
    "pause_ms": 300
  }
  → audio/wav (concatenación con silencios)
- POST /api/v1/conversations con ?stream=true → NDJSON de eventos (opcional, fase posterior)

Tareas
- [ ] ConversationService.generate(turns, pause_ms)
- [ ] Concatenación con pydub o soundfile
- [ ] Validación: 2+ turnos, voces existen, texto no vacío
- [ ] Tests unitarios e integración
- [ ] Ejemplo docs/examples/dialogue.py

DoD
- Conversación 2 turnos → WAV con silencios correctos
- Voz inexistente → 404

---

## Sprint 4 — Emociones (2 días)

Objetivo: control de emoción por síntesis.

Endpoints
- GET /api/v1/emotions → lista soportadas (neutral, happy, sad, angry, surprised)
- POST /api/v1/tts añade emotion e intensity (0.0-1.0)
- POST /api/v1/conversations permite emotion por turno

Tareas
- [ ] Mapeo emotion → parámetros del engine
- [ ] Validación de intensidad
- [ ] Tests parametrizados (pytest.mark.parametrize)
- [ ] Ejemplo docs/examples/tts_emotion.sh

DoD
- Misma frase con happy y sad produce audios distinguibles (test espectral o mock específico)

---

## Sprint 5 — Rendimiento y robustez (3 días)

Objetivo: producción-ready.

Tareas
- [ ] EnginePool con semáforo
- [ ] Streaming de WAV por chunks (StreamingResponse)
- [ ] Limpieza de outputs caducados (background task)
- [ ] Métricas Prometheus
- [ ] Rate limiting (slowapi)
- [ ] Logs estructurados con request_id
- [ ] Stress test con locust en tests/load/

DoD
- 50 RPS sin OOM, p95 < 3× single-request
- Sin fugas de archivos en storage/outputs/

---

## Sprint 6 — Seguridad y DX (2 días)

Tareas
- [ ] API key opcional
- [ ] CORS configurable
- [ ] OpenAPI enriquecida con ejemplos
- [ ] Dockerfile (Linux) + nota Windows Service
- [ ] Guía de despliegue en docs/deployment/
- [ ] CHANGELOG y semver

---

## Backlog (no priorizado)

- Streaming NDJSON para conversaciones largas
- Soporte SSML
- Webhooks para síntesis asíncrona
- Multi-modelo (cambiar idioma sin reinicio)
- Panel web minimalista

