# Configurar Supabase para VIVI

## Arquitectura

VIVI usa una estrategia de persistencia doble:

1. SQLite registra primero la operación y funciona como respaldo recuperable.
2. Supabase PostgreSQL recibe el lead y sus cambios como almacenamiento cloud.
3. Si Supabase falla, la conversación no se pierde y se registra un evento
   local `SUPABASE_SYNC / FAILED`.

Supabase contiene dos tablas:

- `vivi_leads`: formulario, campaña, perfil conversacional, score y estado CRM.
- `vivi_integration_events`: trazabilidad de sincronizaciones y etapas.

## 1. Rotar la clave expuesta

La clave secreta compartida anteriormente debe considerarse comprometida.
Rótala en Supabase antes de continuar. Nunca uses la clave secreta en
Streamlit del navegador, JavaScript, Telegram ni repositorios públicos.

## 2. Crear el esquema

En Supabase abre **SQL Editor**, crea una consulta y ejecuta todo el archivo:

`supabase/migrations/20260726_vivi_schema.sql`

El script:

- crea ambas tablas e índices;
- activa Row Level Security;
- revoca acceso a `anon` y `authenticated`;
- permite acceso al rol de servicio utilizado exclusivamente por el backend.

## 3. Configurar `.env`

En el archivo local `.env` deja una sola ocurrencia de cada variable:

```dotenv
DATA_BACKEND=supabase
SUPABASE_URL=https://TU_PROYECTO.supabase.co
SUPABASE_PUBLISHABLE_KEY=TU_CLAVE_PUBLICABLE
SUPABASE_SECRET_KEY=TU_NUEVA_CLAVE_SECRETA
```

`SUPABASE_PUBLISHABLE_KEY` se conserva para futuras funciones públicas, pero
la persistencia del backend utiliza `SUPABASE_SECRET_KEY`.

Para volver temporalmente a almacenamiento local:

```dotenv
DATA_BACKEND=sqlite
```

## 4. Migrar leads existentes

Con el entorno virtual activo:

```powershell
.\venv\Scripts\python.exe tools\migrate_sqlite_to_supabase.py
```

El proceso usa `upsert` por `lead_code`, por lo que se puede repetir sin crear
leads duplicados. Los eventos históricos permanecen en SQLite; los eventos
nuevos se almacenan en ambas capas.

## 5. Probar

1. Reinicia Streamlit.
2. Envía un formulario de prueba.
3. Confirma en **Table Editor → vivi_leads** el nuevo `lead_code`.
4. Responde en la conversación y verifica que cambien
   `conversation_profile_json`, `propensity_score` y `crm_status`.
5. Revisa `vivi_integration_events`.

## Seguridad

- No subas `.env` ni `leads.db` a GitHub.
- La clave secreta omite RLS y debe existir únicamente en el backend.
- No crees políticas públicas para estas tablas: contienen datos personales.
- Para producción, guarda la clave en un gestor de secretos y cifra los datos
  de documento con una estrategia definida por el responsable de seguridad.
