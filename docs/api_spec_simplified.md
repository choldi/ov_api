# OmniVoice API - Especificación Simplificada

## Resumen

API REST para síntesis de voz (TTS) con soporte para voces stock, clonado zero-shot, control de emoción y conversaciones multi-voz.

**Base URL:** `/api/v1`  
**Formato:** JSON (requests) / audio/wav (responses de audio)  
**Autenticación:** Opcional `X-API-Key` header

---

## Endpoints

### 1. Salud del sistema

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/health` | Health check básico (liveness) |
| GET | `/health/ready` | Readiness check (modelo cargado, GPU, DB) |

**Response 200:**
```json
{
  "status": "ok",
  "gpu": true,
  "model_loaded": true,
  "database": true
}
```

---

### 2. Voces Stock (predefinidas)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/voices/stock` | Listar voces stock disponibles |

**Query params:**
- `language` (opcional): Filtrar por ISO 639-1 (ej: `es`, `en`)

**Response 200:**
```json
[
  {
    "voice_id": "es-mx-male",
    "language": "es",
    "gender": "male",
    "name": "Spanish Male (Mexico)"
  },
  {
    "voice_id": "en-us-female",
    "language": "en",
    "gender": "female",
    "name": "English Female (US)"
  }
]
```

---

### 3. Síntesis de Voz (TTS)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/tts` | Generar audio desde texto |

**Request Body:**
```json
{
  "text": "Hola, ¿cómo estás?",
  "voice_id": "es-mx-male",
  "language": "es",
  "speed": 1.0,
  "emotion": "neutral",
  "emotion_intensity": 0.5,
  "format": "wav"
}
```

**Campos:**
| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `text` | string | Sí | - | Texto a sintetizar (máx 5000 chars) |
| `voice_id` | string | Sí | - | ID de voz (stock o clonada) |
| `language` | string | Sí | - | ISO 639-1 (validado contra voz) |
| `speed` | float | No | 1.0 | Velocidad (0.5 - 2.0) |
| `emotion` | string | No | "neutral" | `neutral`, `happy`, `sad`, `angry`, `surprised` |
| `emotion_intensity` | float | No | 0.5 | Intensidad 0.0 - 1.0 |
| `format` | string | No | "wav" | `wav` o `mp3` |

**Response 200:** `audio/wav` (streaming) o `audio/mpeg`

**Errores:**
- 400: Texto vacío, velocidad inválida, emoción no soportada
- 404: Voz no encontrada
- 422: Idioma no coincide con voz, audio de referencia inválido (si usa voz clonada)
- 503: Motor no disponible (VRAM OOM)

---

### 4. Voces Clonadas (Zero-shot)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/voices/clone` | Crear voz clonada desde audio de referencia |
| GET | `/voices/cloned` | Listar voces clonadas (paginado) |
| GET | `/voices/cloned/{voice_id}` | Obtener detalles de voz clonada |
| DELETE | `/voices/cloned/{voice_id}` | Eliminar voz clonada |

#### POST `/voices/clone`

**Content-Type:** `multipart/form-data`

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `reference_audio` | file | Sí | Audio WAV/MP3 (5-30s, mono, 22050Hz) |
| `name` | string | Sí | Nombre único (3-64 chars, `^[a-zA-Z0-9_-]+$`) |
| `language` | string | Sí | ISO 639-1 |

**Response 201:**
```json
{
  "voice_id": "uuid-v4",
  "name": "mi-voz",
  "language": "es",
  "duration_sec": 12.3,
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### GET `/voices/cloned`

**Query params:**
- `limit` (default 20, max 100)
- `offset` (default 0)

**Response 200:**
```json
{
  "items": [
    {
      "voice_id": "uuid",
      "name": "mi-voz",
      "language": "es",
      "duration_sec": 12.3,
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

---

### 5. Conversaciones Multi-voz

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/conversations` | Generar diálogo entre múltiples voces |

**Request Body:**
```json
{
  "turns": [
    { "voice_id": "es-mx-male", "text": "Hola, ¿cómo estás?" },
    { "voice_id": "en-us-female", "text": "I'm doing great, thanks!" }
  ],
  "pause_ms": 300,
  "format": "wav"
}
```

**Campos:**
| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `turns` | array | Sí | - | Mínimo 2 turnos |
| `turns[].voice_id` | string | Sí | - | Voz stock o clonada |
| `turns[].text` | string | Sí | - | Texto del turno |
| `turns[].emotion` | string | No | "neutral" | Emoción por turno |
| `turns[].emotion_intensity` | float | No | 0.5 | Intensidad por turno |
| `pause_ms` | int | No | 300 | Silencio entre turnos (0-5000) |
| `format` | string | No | "wav" | `wav` o `mp3` |

**Response 200:** `audio/wav` concatenado con silencios

**Errores:**
- 400: Menos de 2 turnos, texto vacío, pausa inválida
- 404: Alguna voz no existe

---

### 6. Emociones Soportadas

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/emotions` | Listar emociones disponibles |

**Response 200:**
```json
[
  { "id": "neutral", "name": "Neutral", "description": "Tono neutro" },
  { "id": "happy", "name": "Feliz", "description": "Tono alegre" },
  { "id": "sad", "name": "Triste", "description": "Tono melancólico" },
  { "id": "angry", "name": "Enojado", "description": "Tono enfadado" },
  { "id": "surprised", "name": "Sorprendido", "description": "Tono de sorpresa" }
]
```

---

## Códigos de Error (RFC 7807)

Todos los errores devuelven `application/problem+json`:

```json
{
  "type": "https://omnivoice.api/errors/voice-not-found",
  "title": "Voice not found",
  "status": 404,
  "detail": "Voice with id 'uuid' does not exist",
  "instance": "/api/v1/tts"
}
```

| Código | Tipo | Cuándo |
|--------|------|--------|
| 400 | `invalid-request` | Parámetros inválidos |
| 404 | `voice-not-found` | Voz no existe |
| 409 | `voice-name-conflict` | Nombre de voz duplicado al clonar |
| 422 | `unsupported-language` | Idioma no soportado por la voz |
| 422 | `invalid-reference-audio` | Audio de referencia inválido (duración, formato, SR) |
| 503 | `engine-unavailable` | Motor ocupado / VRAM OOM |
| 500 | `internal-error` | Error inesperado |

---

## Límites y Rendimiento

| Límite | Valor |
|--------|-------|
| Texto máximo por request | 5000 caracteres |
| Audio referencia (clonado) | 5-30 segundos |
| Tamaño upload máximo | 10 MB |
| Concurrencia motor (P2000) | 1 síntesis simultánea |
| TTL outputs temporales | 1 hora |
| Rate limiting (opcional) | 60 req/min por API key |

---

## Ejemplos de Uso

### cURL - TTS con voz stock
```bash
curl -X POST "http://localhost:8000/api/v1/tts" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hola mundo", "voice_id": "es-mx-male", "language": "es"}' \
  --output output.wav
```

### cURL - Clonar voz
```bash
curl -X POST "http://localhost:8000/api/v1/voices/clone" \
  -F "reference_audio=@reference.wav" \
  -F "name=mi-voz" \
  -F "language=es"
```

### cURL - Conversación
```bash
curl -X POST "http://localhost:8000/api/v1/conversations" \
  -H "Content-Type: application/json" \
  -d '{
    "turns": [
      {"voice_id": "es-mx-male", "text": "Hola"},
      {"voice_id": "cloned-uuid", "text": "Hola, ¿qué tal?"}
    ],
    "pause_ms": 500
  }' \
  --output dialogue.wav
```

### Python - Cliente simple
```python
import httpx

async def tts(text: str, voice_id: str, language: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "http://localhost:8000/api/v1/tts",
            json={"text": text, "voice_id": voice_id, "language": language}
        )
        resp.raise_for_status()
        return resp.content
```

---

## Versionado

- Versión actual: `v1`
- Prefijo obligatorio: `/api/v1`
- Cambios breaking → nueva versión `/api/v2`

---

## Changelog

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0.0 | 2024-01-15 | API inicial simplificada |
