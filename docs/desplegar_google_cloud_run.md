# Desplegar VIVI en Google Cloud Run

## Requisitos

- Un proyecto de Google Cloud con facturación habilitada.
- El esquema de Supabase ya creado.
- Las credenciales rotadas y almacenadas en Secret Manager.

## 1. Abrir Cloud Shell

En `console.cloud.google.com`, selecciona el proyecto y pulsa el icono
**Activar Cloud Shell**. Cloud Shell ya incluye `gcloud`.

## 2. Descargar el código

```bash
git clone https://github.com/danielcramirez/ViviendAI.git
cd ViviendAI
```

Si el repositorio contiene una carpeta adicional `Prototipo`, entra en ella:

```bash
cd Prototipo
```

## 3. Definir proyecto y región

```bash
gcloud config set project TU_PROJECT_ID
gcloud config set run/region southamerica-east1
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com
```

## 4. Crear secretos

Desde **Security → Secret Manager**, crea estos secretos:

- `gemini-api-key`
- `supabase-secret-key`
- `telegram-bot-token`
- `vivi-agent-api-key`

No subas el archivo `.env`.

Otorga a la cuenta de servicio de Cloud Run el rol
**Secret Manager Secret Accessor** para esos secretos.

## 5. Desplegar

```bash
gcloud run deploy vivi-viviendai \
  --source . \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --set-env-vars DATA_BACKEND=supabase,ENVIRONMENT=production,GEMINI_MODEL=gemini-2.5-flash,SUPABASE_URL=https://TU_PROYECTO.supabase.co,TELEGRAM_BOT_USERNAME=ViviendAI_bot \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest,SUPABASE_SECRET_KEY=supabase-secret-key:latest,TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,VIVI_AGENT_API_KEY=vivi-agent-api-key:latest
```

Cloud Build usará el `Dockerfile`, publicará la imagen en Artifact Registry y
Cloud Run mostrará la URL pública al finalizar.

## 6. Verificar

```bash
gcloud run services describe vivi-viviendai \
  --format="value(status.url)"
```

Abre la URL y completa un lead de prueba. Confirma el registro en Supabase.

## Consideraciones

- Cloud Run no garantiza persistencia de archivos locales. `leads.db` es solo
  un respaldo temporal por instancia; Supabase debe ser la fuente principal.
- Una aplicación pública procesa datos personales. Antes de producción agrega
  autenticación, política de privacidad y controles de acceso al panel interno.
- Telegram y Make deben apuntar a URL públicas separadas si se despliega
  también `agent_api.py`; el contenedor actual publica la interfaz Streamlit.
