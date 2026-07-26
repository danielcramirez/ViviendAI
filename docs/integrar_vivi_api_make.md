# Integrar VIVI Agent API con Telegram en Make

Esta integración reemplaza el módulo Gemini directo de Make. Make conserva la
recepción y el envío de Telegram; Python controla catálogo, perfil, scoring y
Gemini.

## 1. Ejecutar la API

Desde `C:\05_DAGEF\30X\Prototipo`:

```powershell
.\venv\Scripts\Activate.ps1
python agent_api.py
```

Comprobar:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Make no puede acceder a `127.0.0.1`. Para una integración real, publica la API
en DigitalOcean, Azure, Render u otro servicio HTTPS. Configura una clave larga
en `VIVI_AGENT_API_KEY`.

## 2. Modificar el escenario de Telegram

Conserva:

`Telegram Watch Updates → Data Store Get Record`

Reemplaza el módulo `Google Gemini AI` por:

`HTTP → Make a request`

Configuración:

- Method: `POST`
- URL: `https://TU_API_PUBLICA/v1/chat`
- Header `Content-Type`: `application/json`
- Header `x-vivi-api-key`: el mismo valor de `VIVI_AGENT_API_KEY`
- Parse response: `Yes`

Body:

```json
{
  "lead_id": "{{ifempty(6.lead_id; 2.message.chat.id)}}",
  "channel": "telegram",
  "customer_name": "{{2.message.from.first_name}}",
  "project_origin": "{{6.project_origin}}",
  "message": "{{2.message.text}}",
  "history": "{{ifempty(6.history; \"\")}}",
  "profile_json": "{{ifempty(6.profile_json; \"{}\")}}"
}
```

## 3. Enviar respuesta a Telegram

En `Telegram Bot → Send a Text Message or Reply`, mapea:

`HTTP → Data → reply`

No mapees `candidates[].content.parts[].text`; Gemini ya no es llamado
directamente desde Make.

## 4. Guardar memoria sin destruir el perfil

En `Data Store → Add/Replace a record`:

- Key: `Telegram → Message → Chat → ID`
- Overwrite: `Yes`
- `lead_id`: `HTTP → Data → profile → lead_code`, con fallback al lead anterior.
- `project_origin`: valor anterior.
- `history`: historial anterior + mensaje del usuario + `HTTP → Data → reply`.
- `profile_json`: serialización completa de `HTTP → Data → profile`.
- `last_score`: `HTTP → Data → scoring → propensity_score`.
- `turn_count`: `add(ifempty(6.turn_count; 0); 1)`.
- `updated_at`: `now`.

Es crítico no volver a escribir `profile_json = {}` ni `last_score = 0`.

## 5. Manejo de errores

Añade un error handler al módulo HTTP:

- 429/502/503: reintento con demora.
- Timeout: enviar una respuesta de respaldo.
- Nunca dejar el mensaje del cliente sin contestar.

Mensaje de respaldo:

> Estoy validando las opciones disponibles para darte información correcta.
> ¿Me confirmas en qué municipio deseas comprar?

## 6. Pruebas de aceptación

1. `¿Qué proyectos hay en Chía con 250 millones?`
   - Debe devolver INARI.
2. `¿Qué hay en Soacha con 200 millones?`
   - Debe devolver La Macarena y Monguí.
3. `No me interesa Samán`
   - Debe conservar el rechazo al proyecto original.
4. Reiniciar el escenario y continuar.
   - Debe recuperar perfil y score.
5. Simular Gemini sin cuota.
   - Las consultas de catálogo deben seguir funcionando.
