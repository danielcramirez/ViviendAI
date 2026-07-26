# VIVI · ViviendAI — Constitución y Especificación Técnica

**Versión del documento:** 2.0  
**Fecha:** 26 de julio de 2026  
**Naturaleza:** Prototipo demostrativo del reto de vivienda Colsubsidio × 30X  
**Metodología:** Spec-Driven Development

---

# PARTE I — CONSTITUCIÓN DEL PROYECTO

## 1. Propósito

Transformar leads fríos de pauta digital (Meta Ads, Instagram, WhatsApp, Telegram) en
perfiles de vivienda enriquecidos, explicables y accionables, entregando al equipo
comercial una **Ficha del Sueño** y un **score de propensión auditable** antes de
cualquier contacto humano.

## 2. Principios de Arquitectura (Innegociables)

### 2.1 Performance
| Capa | Límite | Verificación |
|---|---|---|
| API (`/v1/chat`) | < 2 segundos p99 | Test de carga con Locust |
| Interfaz Streamlit | < 3 segundos TTI | Lighthouse / Playwright |
| Scoring determinístico | < 100 ms | Unit test con perfil completo |
| Consulta a Gemini | < 8 segundos con timeout | Timeout configurable en cliente HTTP |

### 2.2 Escalabilidad
- **Diseño para 10.000 usuarios concurrentes** como meta aspiracional.
- Stateless en la capa de API (`agent_api.py`): toda la sesión vive en la base de
  datos o en el perfil JSON, no en memoria del proceso.
- `ThreadingHTTPServer` para concurrencia en la API del prototipo.
  **Nota:** Python threads no escalan linealmente por el GIL. Para 10K concurrentes
  (aspiracional), el target de producción sería ASGI (FastAPI + Uvicorn) con
  `asyncio`. ThreadingHTTPServer es válido y suficiente para la demo.
- Cache de catálogo con `st.cache_data` en Streamlit.
- La base de datos (SQLite/Supabase) es el cuello de botella reconocido. SQLite es
  válido para prototipo; Supabase con RLS y pool de conexiones es el target de
  producción.

### 2.3 Seguridad (Zero Trust desde la primera migración)
- Toda tabla en Supabase tendrá **RLS (Row Level Security)** habilitado desde la
  primera migración.
- `VIVI_AGENT_API_KEY` validada con `hmac.compare_digest` en cada request a la API.
- Secretos solo en `.env`; `.env.example` con marcadores es el único archivo
  versionado.
- No se almacenan direcciones exactas, contraseñas, números de cuenta bancaria ni
  datos biométricos.
- El consentimiento se registra como booleano con timestamp. La versión de la
  política es un supuesto por validar con el equipo legal.
- Los webhooks de Make usan autenticación por API key.
- Telegram usa token firmado (no solo `lead_code`) como validación de inicio.

### 2.4 Modularidad — Monolito Modular por Dominios
El código se organiza en dominios aislados con dependencias explícitas. Cada dominio
tiene una responsabilidad única y puede probarse de forma independiente:

```
agents/              → Dominio de agentes de IA
core/                → Dominio de lógica de negocio (scoring, finanzas, catálogo)
data/                → Dominio de persistencia (SQLite, Supabase)
integrations/        → Dominio de integraciones externas (Make, Salesforce, pagos)
ui/                  → Dominio de interfaz (Streamlit)
config/              → Configuración estática (catálogo, agents, scoring schema)
schemas/             → Contratos JSON versionados
```

**Regla:** Ningún módulo fuera de su dominio puede importar directamente la
implementación interna de otro dominio. Solo se permite importar servicios públicos
(api pública de cada dominio).

### 2.5 Trazabilidad
- Cada lead conserva `campaign_id`, `adset_id`, `ad_id`, `form_id`, UTM y proyecto
  de origen en toda la cadena.
- Cada evento de integración se registra en `INTEGRATION_EVENTS` con timestamp,
  tipo y estado.
- El scoring es 100% determinístico y explicable: cada punto tiene una razón textual.
- No se usa género, etnia, discapacidad, dirección exacta, empleador, presencia en
  redes sociales ni negativa a responder para puntuar.

### 2.6 Responsabilidad de IA
- Gemini solo se usa para **conversación empática** y **extracción estructurada**.
- Los cálculos financieros, subsidios, scoring y reglas de elegibilidad son
  **determinísticos y están escritos en Python**.
- Si Gemini falla (429, 5xx, timeout), el sistema responde con el **simulador local**
  sin dejar al cliente sin atención.
- No se promete crédito, subsidio ni aprobación. Toda cifra es orientativa.

---

# PARTE II — ESPECIFICACIÓN TÉCNICA (SPEC)

## Bloque 1: Qué hace VIVI

VIVI convierte un lead de pauta digital en un perfil de vivienda completo mediante
el siguiente pipeline:

1. **Captura contextual** — Recibe el lead desde Meta Ads (simulado), Instagram o
   Telegram conservando campaña, anuncio, proyecto, canal y parámetros UTM.
2. **Formulario mínimo** — Solicita solo datos que Meta no entrega: identidad,
   ingresos, afiliación, ahorro declarado, horizonte, preferencias y consentimiento.
3. **Estimación financiera determinística** — Calcula subsidio Colsubsidio potencial,
   concurrente potencial y cuota máxima orientativa (40% del ingreso).
4. **Conversación empática** — VIVI (Consultor Empático) conversa con el lead para
   entender su sueño de vivienda: ubicación, presupuesto, espacios, propósito,
   disposición al contacto. Una pregunta por turno.
5. **Extracción estructurada** — El Analista de Perfilamiento (Agente 2) extrae datos
   de la conversación en formato JSON validado contra `lead_profile.schema.json`.
6. **Score auditable VIVI-1.0** — Motor determinístico que evalúa 6 dimensiones
   (intención, horizonte, preparación financiera, encaje, engagement, siguiente paso)
   y produce una prioridad comercial (ALTA / MEDIA / NUTRICIÓN / TEMPRANO).
7. **Ficha del Sueño** — Diagnóstico textual que resume perfil, score y acción
   recomendada. Se muestra en la interfaz Streamlit.
8. **Enrutamiento comercial** — Si el score es ALTA (≥80) y el lead autoriza contacto,
   se envía el payload enriquecido a Salesforce (simulado) con la Ficha del Sueño.
9. **Seguimiento de embudo** — El asesor puede actualizar estados: NUEVO →
   CONTACTADO → PERFILADO → CITA_AGENDADA → SEPARADO (vía pago simulado).
   También existen NUTRICIÓN y DESCARTADO.
10. **Reportes de campaña** — Efectividad por campaña, proyecto, fuente, con personas
    únicas, duplicados, prioridad alta y separaciones.

## Bloque 2: Qué NO hace VIVI (Anti-Scope)

| Fuera de alcance | Razón |
|---|---|
| Aprobación de crédito hipotecario | No reemplaza a un banco ni a DataCrédito |
| Asignación formal de subsidios | La asignación real exige validación de afiliación, antigüedad, aportes, hogar y requisitos vigentes |
| Consulta a centrales de riesgo | No integra DataCrédito, CIFIN ni TransUnion |
| Consulta de cuentas bancarias | No se piden ni almacenan números de cuenta |
| Consulta de información biométrica | No se almacenan huellas, rostro ni voz |
| Enriquecimiento externo invasivo | No usa Sherlock, Holehe ni scraping de redes sociales para scoring |
| Integración productiva con Meta | Meta Lead Ads es simulada para la demo |
| Integración productiva con SAP HANA Cloud | SQLite actúa como gemelo digital |
| CRM en producción | Salesforce es simulado mediante payload local |
| Chat de voz o Gemini Live | No necesario para MVP del reto |
| Evaluación de crédito de libre inversión | No se usa para calcular subsidio |
| Promesas de precio, disponibilidad o entrega | Los valores monetarios son inferencias analíticas y deben confirmarse contra brochure vigente |
| Portal público de autogestión | La interfaz es una demo; no hay registro público sin campaña |

## Bloque 3: Usuario y momento de intención

### Usuario primario
**Cliente potencial de Colsubsidio** que ha hecho clic en un anuncio de Meta Ads
(Instagram/Facebook/Reels) o llega por canal orgánico (Instagram, Telegram). Su
intención es **explorar opciones de vivienda**, no necesariamente comprar hoy.

### Usuario secundario
**Asesor comercial de Colsubsidio** que recibe un lead perfilado, con score y Ficha
del Sueño, y puede contactar al cliente con contexto completo.

### Momento de intención
El lead llega **frío** (0,2% de conversión actual). VIVI lo calienta mediante
conversación empática antes de pasarlo al asesor. La intención se mide por:
- Interés confirmado en el proyecto de origen
- Propósito de compra expresado
- Aceptación de contacto de asesor
- Autorización de cita

## Bloque 4: Flujo en 7 pasos

```
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 1 · CLIC EN META ADS                                          │
│ Usuario ve anuncio → CTA → Formulario instantáneo                   │
│ Atribución: campaign_id, adset_id, ad_id, form_id, UTM, placement   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 2 · CAPTURA Y PERSISTENCIA                                    │
│ Validación → Normalización → Deduplicación → SQLite                 │
│ Scoring inicial (formulario) → Evento de integración                │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 3 · ESTIMACIÓN FINANCIERA                                     │
│ Subsidio Colsubsidio (30/20 SMMLV)                                  │
│ Concurrente potencial (20 SMMLV)                                    │
│ Cuota máxima orientativa (40% del ingreso)                          │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 4 · CONVERSACIÓN CON VIVI (Agente 1)                          │
│ Consultor Empático: una pregunta por turno                          │
│ Canal: Telegram o Instagram simulado                                │
│ Reglas: no pregunta datos bancarios, dirección exacta, ni promete    │
│ Catálogo consultable por ubicación y presupuesto (Python)           │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 5 · PERFILAMIENTO ESTRUCTURADO (Agente 2)                     │
│ Analista de Perfilamiento:                                          │
│ 1. Recibe historial + perfil actual                                 │
│ 2. Gemini extrae datos en JSON contra schema                        │
│ 3. Valida JSON contra lead_profile.schema.json                      │
│ 4. Ejecuta scoring determinístico VIVI-1.0                          │
│ 5. Persiste perfil + score + eventos                                │
│                                                                     │
│ Trigger del Agente 2: se ejecuta cuando:                            │
│  (a) el Agente 1 detecta ≥2 campos nuevos en profile_updates,      │
│  (b) el lead autoriza contacto de asesor,                           │
│  (c) se completa el turno Nº 5 (perfil completo), o                 │
│  (d) se solicita explícitamente desde la API.                       │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 6 · ENRUTAMIENTO Y FICHA DEL SUEÑO                            │
│ Score ≥ 80 + autorización → Salesforce (simulado)                   │
│ Score 55-79 → Completar perfil                                      │
│ Score 30-54 → Nutrición digital                                     │
│ Score 0-29 → Acompañamiento temprano                                │
│ Se genera Ficha del Sueño (solo Streamlit)                          │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 7 · SEGUIMIENTO HASTA SEPARACIÓN                              │
│ Asesor marca "Listo para separación"                                │
│ Simulación de pasarela de pago (< $1.000.000)                       │
│ Confirmación → Estado SEPARADO en SQLite y Salesforce simulado      │
└─────────────────────────────────────────────────────────────────────┘
```

## Bloque 5: Tres criterios de aceptación verificables

### CA-1: Perfilamiento completo de lead nuevo
**Dado** un lead nuevo que completa el formulario y conversa con VIVI,
**Cuando** el Agente 2 completa la extracción estructurada,
**Entonces** el perfil JSON es válido contra `lead_profile.schema.json`,
el score se calcula con desglose de razones, y la Ficha del Sueño se genera
con diagnóstico textual.

*Verificación:* `python -m unittest test_analista_perfilamiento`

### CA-2: Enrutamiento correcto según score
**Dado** un lead con perfil completo,
**Cuando** el scoring VIVI-1.0 produce un resultado,
**Entonces** el lead se enruta a:
- ALTA (≥80) → Salesforce simulado con payload completo
- MEDIA (55-79) → Bandera "completar perfil"
- NUTRICIÓN (30-54) → Nutrición digital
- TEMPRANO (0-29) → Acompañamiento

*Verificación:* Prueba unitaria que recorre los 4 umbrales.

### CA-3: Simulación de separación con pago
**Dado** un lead en estado CITA_AGENDADA,
**Cuando** el asesor lo marca como "Listo para separación" y se ejecuta
la simulación de pago,
**Entonces** el sistema registra el evento de pago, actualiza el estado a
SEPARADO en SQLite, y dispara el payload a Salesforce simulado con el
evento de separación.

*Verificación:* Prueba end-to-end que recorre CITA_AGENDADA → SEPARADO.

## Bloque 6: Datos que toca y consentimiento

### Datos solicitados explícitamente
| Campo | Tipo | Obligatorio | Notas |
|---|---|---|---|
| Nombre completo | Texto | Sí | Mínimo nombre + apellido |
| Tipo de documento | Select | Sí | CC, CE, Pasaporte |
| Número de documento | Texto | Sí | Alfanumérico, ≥5 caracteres |
| Ingresos mensuales | Número | Sí | En pesos colombianos |
| Tipo de afiliación | Select | Sí | Trabajador, Beneficiario, No afiliado |
| Horizonte de compra | Select | Sí | 4 opciones + "Explorando" |
| Rango de ahorro | Select | Sí | Incluye "Prefiero no responder" |
| Proyecto de origen | Inferido | Sí | Viene de la campaña |
| Habitaciones deseadas | Slider | Sí | 1-4 |
| Usuario Telegram | Texto | No | Opcional |

### Datos conversacionales (extraídos por Agente 2)
| Campo | Origen |
|---|---|
| Interés en proyecto origen | Conversación |
| Proyecto alternativo | Conversación |
| Municipio de residencia | Conversación |
| Zona de trabajo/estudio | Conversación |
| Propósito de compra | Conversación |
| Personas en el hogar | Conversación |
| Sueño de vivienda | Conversación |
| Características deseadas | Conversación |
| Presupuesto de compra | Conversación |
| Contacto de asesor | Conversación (autorización) |
| Aceptación de cita | Conversación (autorización) |

### Datos que NUNCA se almacenan
- Dirección exacta (solo municipio/zona)
- Números de cuenta bancaria
- Contraseñas
- Datos biométricos
- Historial crediticio
- Información de redes sociales no autorizada

### Consentimiento
El consentimiento se registra como:
- `consent`: booleano (checkbox en formulario)
- `consent_timestamp`: ISO 8601 (cuando se marcó)
- El usuario puede retirar la autorización (sin implementación de borrado en
  prototipo; en producción debe haber purge con retención configurable)

**Supuesto por validar:** La versión de la política de tratamiento de datos y su
hash no se implementan en el prototipo. Validar con el equipo legal si el jurado
del reto requiere evidenciar la versión de política aceptada.

## Bloque 7: Supuestos por validar con mentores

| # | Supuesto | Impacto si es incorrecto |
|---|---|---|
| S-01 | **10.000 usuarios concurrentes** son meta aspiracional, no requisito de demo. | Si el jurado espera una prueba de carga, habrá que ajustar el diseño. |
| S-02 | **La versión de política de Habeas Data** no es necesaria para la demo. | Si el jurado evalúa cumplimiento normativo, habrá que agregar versión, hash y fecha de vigencia. |
| S-03 | **SQLite + Supabase** es la combinación aceptable para el prototipo. | Si el jurado espera SAP HANA Cloud real, la arquitectura cambia significativamente. |
| S-04 | **El consultor empático y el analista de perfilamiento** como servicios separados es la arquitectura correcta. | Si hay restricción de costos de Gemini, podríamos unificarlos o reducir llamadas. |
| S-05 | **El pago simulado (< $1M)** como detonante de SEPARADO es aceptable. | Si el jurado espera una integración real con pasarela de pagos, el esfuerzo aumenta. |
| S-06 | **La API Python como orquestador principal** (Make solo para webhooks Telegram) es la dirección correcta. | Si Make debe seguir siendo el orquestador central, la API Python pasa a ser respaldo. |
| S-07 | **El scoring no usa género, etnia, discapacidad, dirección ni empleador.** | Si un mentor sugiere incluir variables socioeconómicas adicionales, debe evaluarse contra la regla 90/10 y la no discriminación. |
| S-08 | **Los leads en NUTRICIÓN y TEMPRANO** no requieren automatización de seguimiento (email/WhatsApp) para la demo. | Si el reto espera demostrar nutrición automatizada, habrá que integrar un servicio de email o WhatsApp. |

---

# PARTE III — ARQUITECTURA Y STACK

## Stack tecnológico

| Capa | Tecnología | Uso |
|---|---|---|
| Frontend | **Streamlit** ≥1.57 | Interfaz de demo, centro de operaciones, chat simulado |
| API Orquestadora | **Python 3.12+** (`agent_api.py`) | API REST principal con `ThreadingHTTPServer` |
| Agente 1 (Consultor) | **Gemini API** (vía `google-generativeai` o REST directo) | Conversación empática y extracción estructurada |
| Agente 2 (Analista) | **Gemini API** + **Python** | Extracción JSON + validación + scoring determinístico |
| Persistencia local | **SQLite** | Gemelo digital de SAP HANA Cloud |
| Persistencia producción | **Supabase** (PostgreSQL + RLS) | Datos permanentes, sesiones, scores, eventos |
| Webhooks / Canales | **Make** | Recepción y envío de Telegram (solo webhooks) |
| CRM | **Salesforce** (simulado) | Payload JSON local con mapeo de campos |
| AI Gateway | N/A (directo a Gemini API) | En producción, considerar Azure API Management |

## Estructura de carpetas propuesta

```
Prototipo/
│
├── app.py                          # Streamlit frontend (punto de entrada demo)
├── agent_api.py                    # API REST (orquestador principal, ThreadingHTTPServer)
├── requirements.txt                # Dependencias Python
├── .env                            # Secretos (NUNCA versionar)
├── .env.example                    # Template de secretos
│
├── agents/                         # ★ DOMINIO: AGENTES DE IA
│   ├── __init__.py
│   ├── consultor_empatico.py       # Agente 1: VIVI conversacional + catálogo
│   └── analista_perfilamiento.py   # Agente 2: extracción + validación JSON
│
├── core/                           # ★ DOMINIO: LÓGICA DE NEGOCIO
│   ├── __init__.py
│   ├── profiling_service.py        # Scoring VIVI-1.0 determinístico
│   ├── finance_service.py          # Cálculos financieros y subsidios
│   └── catalog_service.py          # Catálogo de proyectos
│
├── data/                           # ★ DOMINIO: PERSISTENCIA
│   ├── __init__.py
│   ├── lead_service.py             # SQLite (gemelo digital SAP HANA)
│   └── supabase_service.py         # Conexión Supabase (target producción)
│
├── integrations/                   # ★ DOMINIO: INTEGRACIONES EXTERNAS
│   ├── __init__.py
│   ├── make_service.py             # Cliente HTTP para webhooks Make
│   ├── salesforce_service.py       # Construcción y envío payload Salesforce
│   └── payment_simulator.py        # Simulación de pago < $1M para SEPARADO
│
├── ui/                             # ★ DOMINIO: INTERFAZ
│   ├── __init__.py
│   ├── components.py               # Componentes reutilizables Streamlit
│   ├── styles.py                   # CSS y temas
│   └── instagram_simulator.py      # Chat Instagram simulado
│
├── config/                         # Configuración estática versionada
│   ├── agents.json                 # Personalidad y límites de agentes
│   ├── project_catalog.json        # Catálogo de proyectos (26 proyectos)
│   ├── scoring.json                # Dimensiones, pesos, umbrales
│   └── salesforce_fields.json      # Mapeo de campos Salesforce
│
├── schemas/                        # Contratos JSON versionados
│   ├── __init__.py
│   └── lead_profile.schema.json    # Esquema del perfil de lead
│
├── tests/                          # Pruebas unitarias (espejo de /dominios)
│   ├── test_agent_api.py
│   ├── test_consultor_empatico.py
│   ├── test_analista_perfilamiento.py
│   ├── test_profiling_service.py
│   ├── test_finance_service.py
│   ├── test_catalog_service.py
│   ├── test_lead_service.py
│   ├── test_supabase_service.py    # Mock de Supabase
│   ├── test_make_service.py
│   ├── test_payment_simulator.py
│   ├── test_instagram_simulator.py
│   └── test_app.py
│
├── docs/                           # Documentación técnica
│   ├── auditoria_tecnica.md        # Auditoría integral del prototipo
│   ├── configurar_agentes.md       # Configuración de Make, Telegram, Gemini
│   └── integrar_vivi_api_make.md   # Integración API Python con Make
│
├── assets/                         # Recursos estáticos
│   └── vivi-avatar.svg
│
├── tools/                          # Utilidades
│   └── generar_documentacion_pdf.py
│
└── .streamlit/                     # Configuración de Streamlit
    └── config.toml
```

### Reglas de dependencia entre dominios
```
ui/ ──────► agent_api.py ──────► agents/ ──────► core/
  │                                      │           │
  │                                      ▼           ▼
  └──────────────────────────────► data/ ────► integrations/
```
- `ui/` solo importa `agent_api.py` y sus propios componentes
- `agent_api.py` orquesta todos los dominios
- `agents/` importa `core/` (scoring, finanzas, catálogo)
- `agents/` importa `data/` (persistencia)
- `data/` importa `integrations/` (Make, Salesforce, pagos)
- `core/` NO importa `agents/`, `data/` ni `integrations/` (regla estricta)

> La migración de archivos actuales a la nueva estructura se documenta en
> [`MIGRATION_PLAN.md`](./MIGRATION_PLAN.md) para mantener el SPEC enfocado en la
> especificación del sistema destino.

---

# PARTE IV — REGISTRO DE DECISIONES DE ARQUITECTURA (ADR)

## ADR-001: API Python como orquestador principal

**Contexto:** Make era el orquestador original, pero la lógica de negocio creció en
Python y Make se convirtió en un intermediario costoso y con limitaciones de
depuración.

**Decisión:** `agent_api.py` (Python, ThreadingHTTPServer) es el orquestador
principal. Make solo recibe webhooks de Telegram y los reenvía a la API Python.

**Consecuencias:**
- Menos dependencia de Make (costo, límites de ejecución)
- Depuración y logging más ricos
- Make sigue siendo necesario para recibir webhooks de Telegram (no hay sustituto
  gratuito en Python puro)
- La API debe estar publicada en HTTPS para Make (ngrok para desarrollo, DigitalOcean/
  Azure/Render para demo)

## ADR-002: Agente 2 separado del Agente 1

**Contexto:** Originalmente el scoring se llamaba desde el Agente 1 después de cada
turno, mezclando responsabilidades.

**Decisión:** El Analista de Perfilamiento (Agente 2) es un servicio independiente
que:
1. Recibe el historial completo + perfil actual
2. Llama a Gemini con un prompt específico de extracción estructurada
3. Valida el JSON contra `lead_profile.schema.json`
4. Ejecuta el scoring determinístico
5. Persiste en SQLite y/o Supabase

**Consecuencias:**
- Cada agente tiene un prompt y propósito específico
- El Agente 2 puede ejecutarse bajo demanda (no necesariamente después de cada turno)
- Mayor costo de Gemini (2 llamadas por turno vs 1) — mitigado con umbral de
  perfilamiento (ejecutar Agente 2 cada 3 turnos o al completar perfil)

## ADR-003: Supabase como persistencia de producción

**Contexto:** SQLite es el gemelo digital de SAP HANA Cloud para el prototipo, pero
no escala a múltiples canales concurrentes.

**Decisión:** Supabase (PostgreSQL + RLS) es el target de persistencia para la demo.
SQLite se mantiene como respaldo local y para desarrollo offline.

**Consecuencias:**
- Migración de esquemas de SQLite a PostgreSQL
- RLS desde la primera migración
- Autenticación opcional vía Supabase Auth para el centro de operaciones
- Mayor complejidad de setup (variables de entorno, migraciones)

## ADR-004: Separación detonada por pago simulado

**Contexto:** El reto exige cubrir "hasta la separación del inmueble". Un mero
cambio de estado manual no demuestra el flujo financiero.

**Decisión:** El estado SEPARADO se alcanza solo después de una simulación de pago
(< $1.000.000) que confirma la intención de compra. El flujo es:
1. Asesor marca "Listo para separación"
2. Sistema muestra simulación de pasarela de pago
3. "Pago confirmado" → estado SEPARADO en SQLite y Salesforce simulado

**Consecuencias:**
- Mayor realismo en la demo
- Requiere nuevo módulo `integrations/payment_simulator.py`
- El campo `funnel_status` necesita evento de pago asociado

---

### Estado de implementación

| Criterio | Estado | Dependencia |
|---|---|---|
| CA-1: Perfilamiento completo de lead nuevo | ✅ Implementado (v1 vigente) | Usa `profiling_service.py` + `vivi_agent_service.py` |
| CA-2: Enrutamiento correcto según score | ✅ Implementado (v1 vigente) | `calculate_propensity()` con 4 umbrales |
| CA-3: Separación con pago simulado | 🔄 No implementado | Requiere `integrations/payment_simulator.py` (creación planificada) |

---

*Fin del documento — Versión 2.0 — 26 de julio de 2026*
