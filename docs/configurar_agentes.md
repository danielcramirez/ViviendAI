# Configuración de los agentes de VIVI · ViviendAI

## 1. Completar secretos

Edita `.env`. No compartas ni publiques ese archivo. `.env.example` sí puede
subirse a GitHub porque solo contiene marcadores.

## 2. Crear el bot de Telegram

1. Abre `@BotFather` en Telegram.
2. Ejecuta `/newbot`.
3. Guarda el token en `TELEGRAM_BOT_TOKEN`.
4. Guarda el usuario sin `@` en `TELEGRAM_BOT_USERNAME`.
5. El usuario debe iniciar la conversación mediante:

   `https://t.me/<bot>?start=<token_firmado_del_lead>`

Telegram no permite que el bot inicie una conversación con una persona que nunca
abrió el chat.

## 3. Escenario de Make

Orden recomendado:

1. Telegram Bot — Watch Updates.
2. Verificar y resolver el token del parámetro `/start`.
3. Consultar el estado de conversación en Supabase.
4. Enviar mensaje y contexto al Consultor Empático.
5. Enviar la conversación al Analista de Perfilamiento.
6. Validar el JSON contra `schemas/lead_profile.schema.json`.
7. Ejecutar el scoring determinístico de `config/scoring.json`.
8. Insertar perfil y evento de score en Supabase.
9. Responder al usuario mediante Telegram Bot — Send a Text Message.
10. Si el resultado es HOT, notificar al asesor y simular Salesforce.

## 4. Tablas de Supabase

- `telegram_conversations`
- `lead_profiles`
- `lead_score_events`
- `campaign_attribution`
- `advisor_handoffs`

Usa Row Level Security. La `SUPABASE_SECRET_KEY` solo puede existir en el
backend o en el almacén de secretos de Make. Si una clave secreta se publica
en un chat, issue o commit, debe rotarse antes de continuar.

## 5. Archivos editables

- `config/agents.json`: personalidad, límites y preguntas.
- `config/scoring.json`: pesos y rutas comerciales.
- `config/salesforce_fields.json`: mapeo del CRM.
- `schemas/lead_profile.schema.json`: contrato estructurado.
- `.env`: credenciales locales.
