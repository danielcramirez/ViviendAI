# VIVI · ViviendAI

Prototipo interactivo para convertir leads de campañas Meta en perfiles de
vivienda explicables y accionables antes de entregarlos al equipo comercial.

## Alcance implementado

`Meta simulado → formulario Streamlit → Supabase/SQLite → VIVI/Gemini →
scoring determinístico → Salesforce simulado`

- Conserva campaña, anuncio, proyecto, canal y parámetros UTM.
- Calcula subsidios y capacidad de pago mediante reglas determinísticas.
- Mantiene conversaciones en Telegram y en un Instagram simulado.
- Genera la Ficha del Sueño y un score auditable entre 0 y 100.
- Usa Supabase PostgreSQL como nube seleccionable y SQLite como respaldo local.
- Emula Salesforce con un payload auditable antes de la entrega comercial.

No hay conexión productiva con Meta, SAP HANA Cloud ni Salesforce. Supabase
puede operar como persistencia real del prototipo. Make Data Store conserva la
memoria temporal de Telegram; Supabase conserva leads, scoring y trazabilidad.

La prioridad comercial no es aprobación de crédito ni asignación de subsidio.
El prototipo no consulta DataCrédito, Holehe, Sherlock ni información bancaria.

## Ejecutar en Windows

```powershell
.\venv\Scripts\Activate.ps1
streamlit run app.py
```

Luego abre `http://localhost:8501`.

## Agente directo y API para Telegram

VIVI consulta `config/project_catalog.json` mediante reglas Python y usa Gemini
solamente para conversación y extracción estructurada. Para ejecutar la API:

```powershell
.\venv\Scripts\Activate.ps1
python agent_api.py
```

La salud del servicio queda disponible en `http://127.0.0.1:8000/health`.
Consulta `docs/integrar_vivi_api_make.md` para sustituir el módulo Gemini de
Make por una llamada HTTP a esta API.

## Pruebas

```powershell
.\venv\Scripts\python.exe -m unittest -v
```

La base local `leads.db` se crea automáticamente. Para activar Supabase y
migrar los registros existentes consulta `docs/configurar_supabase.md`.

## Seguridad

Las credenciales viven solamente en `.env`, que está excluido de Git. Antes de
una demo pública se deben rotar las claves que hayan sido mostradas en capturas
o conversaciones, configurar `TELEGRAM_WEBHOOK_SECRET` y, opcionalmente,
proteger el webhook de Make con `MAKE_WEBHOOK_API_KEY`.

## Documentación

- `spec.md`: constitución y límites del producto.
- `docs/configurar_agentes.md`: configuración de Make, Telegram y Gemini.
- `docs/auditoria_tecnica.md`: estado verificado, brechas y hoja de ruta.
- `docs/configurar_supabase.md`: esquema, seguridad, activación y migración.
