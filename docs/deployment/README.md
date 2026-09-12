# Guía de Despliegue — OmniVoice API

## Requisitos previos

- Python 3.12+
- GPU NVIDIA con CUDA 12.4+ (para motor real)
- OmniVoice instalado externamente
- uv (package manager)

## Despliegue con Docker

### Construir la imagen

```bash
docker build -t omnivoice-api .
```

### Ejecutar

```bash
docker run -d \
  --gpus all \
  -p 8000:8000 \
  -e OMNIVOICE_PATH=/path/to/omnivoice \
  -e OMNIVOICE_FALLBACK_TO_MOCK=false \
  -e API_KEY=tu-api-key-segura \
  -e CORS_ORIGINS=https://tu-dominio.com \
  --name omnivoice-api \
  omnivoice-api
```

### Variables de entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `OMNIVOICE_MODEL_ID` | Modelo a usar (HuggingFace) | `ModelsLab/omnivoice-singing` |
| `OMNIVOICE_PATH` | Ruta a la instalación de OmniVoice | Requerida |
| `OMNIVOICE_FALLBACK_TO_MOCK` | Fallback a mock si el engine falla | `true` |
| `API_KEY` | API key opcional (vacío = sin auth) | `""` |
| `CORS_ORIGINS` | Orígenes CORS permitidos (separados por coma) | `*` |
| `DATABASE_URL` | URL de SQLite para voces clonadas | `sqlite+aiosqlite:///storage/omnivoice.db` |

## Despliegue sin Docker (Linux)

### Instalar dependencias

```bash
# Instalar uv
pip install uv

# Instalar proyecto
uv sync

# Instalar OmniVoice (si no está instalado)
pip install git+https://github.com/omnivoice/omnivoice.git
```

### Ejecutar con systemd

Crear `/etc/systemd/system/omnivoice-api.service`:

```ini
[Unit]
Description=OmniVoice API
After=network.target

[Service]
Type=simple
user=omnivoice
workingdirectory=/opt/omnivoice-api
environment=OMNIVOICE_PATH=/opt/omnivoice
ExecStart=/opt/omnivoice-api/.venv/bin/uvicorn omnivoice_api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Habilitar e iniciar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable omnivoice-api
sudo systemctl start omnivoice-api
```

## Despliegue en Windows (Windows Service)

Usar [NSSM](https://nssm.cc/) o [WinSW](https://github.com/winsw/winsw):

```bash
# Con NSSM
nssm install OmniVoiceAPI C:\Python312\python.exe -m uvicorn omnivoice_api.main:app --host 0.0.0.0 --port 8000
nssm set OmniVoiceAPI AppDirectory C:\omnivoice-api
nssm set OmniVoiceAPI AppEnvironment OMNIVOICE_PATH=C:\omnivoice
nssm start OmniVoiceAPI
```

## Verificación post-despliegue

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Liveness
curl http://localhost:8000/api/v1/health/live

# Readiness
curl http://localhost:8000/api/v1/health/ready

# Listar voces stock
curl http://localhost:8000/api/v1/voices/stock

# Listar emociones soportadas
curl http://localhost:8000/api/v1/emotions

# Probar TTS
curl -X POST http://localhost:8000/api/v1/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Hola mundo","voice_id":"es-mx-male","language":"es"}' \
  --output test.wav

# Probar TTS con emoción
curl -X POST http://localhost:8000/api/v1/tts \
  -H "Content-Type: application/json" \
  -d '{"text":"¡Qué alegría!","voice_id":"es-mx-male","language":"es","emotion":"happy"}' \
  --output happy.wav
```

## Monitoreo

- **Métricas**: `GET /metrics` (Prometheus)
- **Docs**: `GET /docs` (Swagger UI)
- **OpenAPI**: `GET /openapi.json`
