# Estado de las Fases

- [x] Sprint 0 — Setup (1 día)
  - [x] Crear pyproject.toml con dependencias pinned
  - [x] settings.py con pydantic-settings
  - [x] main.py mínimo con /health
  - [x] conftest.py base + fixture de cliente async
  - [x] Makefile con make test, make lint, make run
  - [x] Validar GPU detectada por PyTorch (torch.cuda.is_available())
  - [x] README con quickstart
  - [x] Variable de entorno OMNIVOICE_PATH para localizar instalación externa
  - [x] Módulo omnivoice_api.core con engine_paths, engine_client, exceptions
  - [x] /api/v1/health, /api/v1/health/live, /api/v1/health/ready operativos
  - [x] Tests smoke verdes (test_health_endpoint_returns_ok, test_liveness_endpoint, test_readiness_endpoint_*)

- [x] Sprint 1 — MVP: TTS con voz stock (2 días) 🎯 MVP
  - [x] OmniVoiceEngineInterface (Protocol)
  - [x] OmniVoiceEngine concreto (singleton, warm-up)
  - [x] TtsService.synthesize_stock(...)
  - [x] Router tts.py + voices.py (sólo stock)
  - [x] Manejo de UnsupportedLanguage, VoiceNotFound
  - [x] Tests unitarios del servicio (engine mockeado)
  - [x] Tests de integración con audio real generado
  - [x] Ejemplo en docs/examples/curl_tts_stock.sh

- [ ] Sprint 2 — Clonado de voces (3 días)
- [ ] Sprint 3 — Conversaciones multi-voz (2 días)
- [ ] Sprint 4 — Emociones (2 días)
- [ ] Sprint 5 — Rendimiento y robustez (3 días)
- [ ] Sprint 6 — Seguridad y DX (2 días)
```