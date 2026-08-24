# OmniVoice API

API REST para síntesis de voz (TTS) multilingüe, clonado de voz zero-shot y control de emoción, basada en **OmniVoice (k2-fsa)**.

## Características

- 🎙️ **TTS multilingüe** con voces stock predefinidas
- 🔄 **Clonado de voz zero-shot** a partir de 5-30s de audio de referencia
- 😊 **Control de emoción** (neutral, happy, sad, angry, surprised) con intensidad ajustable
- 💬 **Conversaciones multi-voz** con turnos y pausas configurables
- ⚡ **Optimizado para GPU** (NVIDIA P2000, 5GB VRAM) con concurrencia controlada
- 📦 **Persistencia SQLite** para metadatos de voces clonadas
- 📊 **Observabilidad** con logs estructurados y métricas Prometheus

## Requisitos

- Python 3.11+
- NVIDIA GPU con CUDA 11.8+ (recomendado) o CPU
- 5GB+ VRAM para inferencia en GPU
- FFmpeg (para conversión de audio con pydub)

## Instalación rápida

```bash
# Clonar repositorio
git clone <repo-url>
cd omnivoice-api

# Crear entorno virtual e instalar dependencias
make install

# Verificar GPU
make check-gpu

# Descargar modelo (placeholder - implementar según fuente real)
make download-model

# Iniciar en modo desarrollo
make dev
```

La API estará disponible en:
- **API**: http://localhost:8000/api/v1
- **Docs (Swagger)**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **Health**: http://localhost:8000/api/v1/health

## Configuración

Copia `.env.example` a `.env` y ajusta:

```bash
cp .env.example .env
# Editar .env con tus valores
```

Variables principales:
| Variable | Descripción | Default |
|----------|-------------|---------|
| `OMNIVOICE_MODEL_PATH` | Ruta al modelo OmniVoice | `models/omnivoice` |
| `OMNIVOICE_DEVICE` | Dispositivo de inferencia | `cuda:0` |
| `DATABASE_URL` | URL de SQLite | `sqlite:///storage/omnivoice.db` |
| `API_KEY` | API Key opcional | `None` |
| `LOG_LEVEL` | Nivel de logging | `INFO` |

## Endpoints principales

### Health
- `GET /api/v1/health` - Estado general + GPU
- `GET /api/v1/health/live` - Liveness probe
- `GET /api/v1/health/ready` - Readiness probe

### Voces Stock (Sprint 1)
- `GET /api/v1/voices/stock` - Lista voces disponibles
- `POST /api/v1/tts` - Síntesis con voz stock

### Voces Clonadas (Sprint 2)
- `POST /api/v1/voices/clone` - Clonar voz (multipart)
- `GET /api/v1/voices/cloned` - Listar voces clonadas
- `GET /api/v1/voices/cloned/{id}` - Detalle voz clonada
- `DELETE /api/v1/voices/cloned/{id}` - Eliminar voz clonada

### Conversaciones (Sprint 3)
- `POST /api/v1/conversations` - Generar diálogo multi-voz

### Emociones (Sprint 4)
- `GET /api/v1/emotions` - Emociones soportadas
- `POST /api/v1/tts` - Añade `emotion` e `intensity`

## Ejemplos de uso

### TTS con voz stock
```bash
curl -X POST "http://localhost:8000/api/v1/tts" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hola, esto es una prueba.", "voice_id": "es-mx-male", "language": "es"}' \
  --output output.wav
```

### Clonar voz
```bash
curl -X POST "http://localhost:8000/api/v1/voices/clone" \
  -F "reference=@reference.wav" \
  -F "name=mi_voz" \
  -F "language=es"
```

### Conversación multi-voz
```bash
curl -X POST "http://localhost:8000/api/v1/conversations" \
  -H "Content-Type: application/json" \
  -d '{
    "turns": [
      {"voice_id": "voz_1", "text": "Hola, ¿cómo estás?"},
      {"voice_id": "voz_2", "text": "Muy bien, gracias. ¿Y tú?"}
    ],
    "pause_ms": 300
  }' \
  --output dialogue.wav
```

## Estructura del proyecto

```
omnivoice-api/
├── omnivoice_api/          # Código principal
│   ├── api/v1/             # Routers FastAPI
│   ├── core/               # Engine wrapper, exceptions
│   ├── models/             # Modelos Pydantic/SQLAlchemy
│   ├── repositories/       # Capa de persistencia
│   ├── services/           # Lógica de negocio
│   ├── settings.py         # Configuración
│   └── main.py             # Entry point
├── tests/                  # Tests unitarios e integración
├── storage/                # Datos persistentes (gitignored)
│   ├── voices/             # Voces clonadas
│   ├── outputs/            # Audios generados (TTL 1h)
│   └── cache/              # Embeddings cache
├── models/                 # Modelos OmniVoice (gitignored)
├── docs/                   # Documentación
├── pyproject.toml
├── Makefile
└── README.md
```

## Desarrollo

```bash
# Tests
make test

# Linting + type checking
make lint

# Formateo automático
make format

# Servidor desarrollo con reload
make dev
```

## Despliegue

### Docker (Linux)
```dockerfile
# Dockerfile incluido en el repo
docker build -t omnivoice-api .
docker run -d --gpus all -p 8000:8000 -v ./storage:/app/storage omnivoice-api
```

### Windows Service / Producción
Ver `docs/deployment/` para guías detalladas con Nginx/Caddy y systemd/NSSM.

## Licencia

MIT License - ver `LICENSE` para detalles.
