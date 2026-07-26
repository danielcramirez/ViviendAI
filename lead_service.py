from __future__ import annotations

import json
import sqlite3
import time
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from finance_service import calculate_financial_profile
from supabase_service import (
    fetch_events as fetch_supabase_events,
    fetch_leads as fetch_supabase_leads,
    insert_event as insert_supabase_event,
    patch_lead as patch_supabase_lead,
    upsert_lead as upsert_supabase_lead,
    use_supabase,
)

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "leads.db"


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with _connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS META_LEADS_CAPTURE (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_code TEXT UNIQUE,
                full_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                id_type TEXT NOT NULL,
                income_range TEXT NOT NULL,
                affiliated INTEGER NOT NULL CHECK (affiliated IN (0, 1)),
                negative_report INTEGER NOT NULL CHECK (negative_report IN (0, 1)),
                source TEXT NOT NULL,
                campaign TEXT NOT NULL,
                score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
                rating TEXT NOT NULL,
                duplicate_of TEXT,
                crm_status TEXT NOT NULL DEFAULT 'PENDING',
                crm_payload TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS INTEGRATION_EVENTS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_code TEXT,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_leads_name
                ON META_LEADS_CAPTURE(normalized_name);
            CREATE INDEX IF NOT EXISTS idx_leads_crm_status
                ON META_LEADS_CAPTURE(crm_status);
            """
        )
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(META_LEADS_CAPTURE)").fetchall()
        }
        new_columns = {
            "id_number": "TEXT",
            "affiliation_type": "TEXT",
            "purchase_horizon": "TEXT",
            "savings_range": "TEXT",
            "preferred_project": "TEXT",
            "bedrooms": "INTEGER",
            "commercial_summary": "TEXT",
            "income_monthly": "INTEGER",
            "campaign_id": "TEXT",
            "adset_id": "TEXT",
            "ad_id": "TEXT",
            "form_id": "TEXT",
            "meta_lead_id": "TEXT",
            "utm_source": "TEXT",
            "utm_medium": "TEXT",
            "utm_campaign": "TEXT",
            "utm_content": "TEXT",
            "funnel_status": "TEXT DEFAULT 'NUEVO'",
            "colsubsidio_subsidy": "INTEGER DEFAULT 0",
            "concurrent_potential": "INTEGER DEFAULT 0",
            "max_monthly_payment": "INTEGER DEFAULT 0",
            "telegram_username": "TEXT",
            "conversation_profile_json": "TEXT",
            "propensity_score": "INTEGER DEFAULT 0",
            "propensity_priority": "TEXT",
            "profile_diagnosis": "TEXT",
            "profile_completed_at": "TEXT",
            "consent": "INTEGER DEFAULT 0",
        }
        for column, sql_type in new_columns.items():
            if column not in existing_columns:
                connection.execute(
                    f"ALTER TABLE META_LEADS_CAPTURE ADD COLUMN {column} {sql_type}"
                )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_leads_id_number "
            "ON META_LEADS_CAPTURE(id_number)"
        )


def _normalize_name(value: str) -> str:
    compact = " ".join(value.strip().split())
    without_accents = "".join(
        character
        for character in unicodedata.normalize("NFKD", compact)
        if not unicodedata.combining(character)
    )
    return without_accents.casefold()


def _score(payload: dict[str, Any]) -> tuple[int, str, str]:
    income_scores = {
        "Hasta 2 SMMLV": 30,
        "Entre 2 y 4 SMMLV": 25,
        "Más de 4 SMMLV": 10,
        # Compatibilidad con capturas de la versión inicial.
        "Menos de 1 SMLV": 10,
        "Entre 1 y 2 SMLV": 30,
        "Entre 2 y 4 SMLV": 25,
        "Más de 4 SMLV": 10,
    }
    score = income_scores.get(payload["income_range"], 0)
    affiliation = payload.get("affiliation_type")
    if not affiliation:
        affiliation = "Afiliado como trabajador" if payload.get("affiliated") else "No afiliado"
    score += {
        "Afiliado como trabajador": 30,
        "Beneficiario": 20,
        "No afiliado": 5,
    }.get(affiliation, 0)
    score += {
        "En los próximos 6 meses": 25,
        "Entre 6 y 12 meses": 15,
        "En más de 12 meses": 8,
        "Estoy explorando": 5,
    }.get(payload.get("purchase_horizon"), 10)
    score += {
        "Más de $10 millones": 15,
        "Entre $3 y $10 millones": 10,
        "Menos de $3 millones": 5,
        "Aún no tengo ahorro": 0,
        "Prefiero no responder": 0,
    }.get(payload.get("savings_range"), 5)
    score = min(score, 100)

    if score >= 80:
        return score, "ALTA", "Asignar asesor de vivienda y contactar en menos de 15 minutos."
    if score >= 50:
        return score, "MEDIA", "Continuar perfilación y orientar sobre subsidio y financiación."
    return score, "NUTRICIÓN", "Acompañar el sueño de vivienda y madurar el interés sin descartar al usuario."


def _split_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if len(parts) == 1:
        return "", parts[0]
    return " ".join(parts[:-1]), parts[-1]


def _salesforce_payload(lead: dict[str, Any], lead_code: str) -> dict[str, Any]:
    first_name, last_name = _split_name(lead["full_name"])
    return {
        "FirstName": first_name,
        "LastName": last_name,
        "Company": "Persona natural",
        "LeadSource": "Meta Ads",
        "Tipo_Documento__c": lead["id_type"],
        "Numero_Documento__c": lead.get("id_number", ""),
        "Rango_Ingresos__c": lead["income_range"],
        "Tipo_Afiliacion__c": lead.get("affiliation_type", "No informado"),
        "Horizonte_Compra__c": lead.get("purchase_horizon", "No informado"),
        "Ahorro_Declarado__c": lead.get("savings_range", "No informado"),
        "Proyecto_Origen__c": lead.get("preferred_project", "Por recomendar"),
        "Habitaciones_Deseadas__c": lead.get("bedrooms"),
        "Ingreso_Hogar__c": lead.get("income_monthly", 0),
        "Subsidio_Colsubsidio_Estimado__c": lead.get("colsubsidio_subsidy", 0),
        "Subsidio_Concurrente_Potencial__c": lead.get("concurrent_potential", 0),
        "Cuota_Maxima_Orientativa__c": lead.get("max_monthly_payment", 0),
        "Meta_Lead_ID__c": lead.get("meta_lead_id", ""),
        "Campaign_ID__c": lead.get("campaign_id", ""),
        "Ad_Set_ID__c": lead.get("adset_id", ""),
        "Ad_ID__c": lead.get("ad_id", ""),
        "Form_ID__c": lead.get("form_id", ""),
        "UTM_Source__c": lead.get("utm_source", ""),
        "UTM_Medium__c": lead.get("utm_medium", ""),
        "UTM_Campaign__c": lead.get("utm_campaign", ""),
        "UTM_Content__c": lead.get("utm_content", ""),
        "Resumen_del_Sueno__c": lead.get("commercial_summary", ""),
        "Consentimiento_Datos__c": bool(lead.get("consent", False)),
        "Codigo_Externo__c": lead_code,
    }


def _event(
    connection: sqlite3.Connection,
    lead_code: str,
    event_type: str,
    status: str,
    details: dict[str, Any] | str,
) -> None:
    connection.execute(
        """
        INSERT INTO INTEGRATION_EVENTS
            (lead_code, event_type, status, details, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            lead_code,
            event_type,
            status,
            json.dumps(details, ensure_ascii=False) if isinstance(details, dict) else details,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )


def _local_lead(lead_code: str) -> dict[str, Any]:
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM META_LEADS_CAPTURE WHERE lead_code = ?",
            (lead_code,),
        ).fetchone()
    if not row:
        raise ValueError(f"No existe el lead {lead_code}.")
    return dict(row)


def _register_sync_failure(lead_code: str, operation: str, error: Exception) -> None:
    """Keep the demo available and leave an auditable local error."""
    with _connection() as connection:
        _event(
            connection,
            lead_code,
            "SUPABASE_SYNC",
            "FAILED",
            {"operation": operation, "error": str(error)[:500]},
        )


def _sync_full_lead(lead_code: str) -> str | None:
    if not use_supabase():
        return None
    try:
        upsert_supabase_lead(_local_lead(lead_code))
        insert_supabase_event(
            lead_code,
            "SUPABASE_SYNC",
            "SUCCESS",
            {"operation": "UPSERT_LEAD"},
        )
    except RuntimeError as error:
        _register_sync_failure(lead_code, "UPSERT_LEAD", error)
        return str(error)
    return None


def get_storage_status() -> dict[str, Any]:
    """Expose a safe status without returning URLs or credentials."""
    enabled = use_supabase()
    return {
        "backend": "supabase" if enabled else "sqlite",
        "cloud_enabled": enabled,
        "local_backup": str(DB_PATH),
    }


def capture_lead(payload: dict[str, Any], simulate_latency: float = 1.5) -> dict[str, Any]:
    init_db()
    required = {
        "full_name",
        "id_type",
        "income_range",
        "affiliated",
        "negative_report",
        "source",
        "campaign",
    }
    missing = required.difference(payload)
    if missing:
        raise ValueError(f"Faltan campos obligatorios: {', '.join(sorted(missing))}")

    full_name = " ".join(str(payload["full_name"]).strip().split())
    if not full_name:
        raise ValueError("El nombre no puede estar vacío.")

    time.sleep(max(0, simulate_latency))
    normalized_name = _normalize_name(full_name)
    financial = calculate_financial_profile(
        int(payload.get("income_monthly", 0)),
        payload.get("affiliation_type", ""),
    )
    if payload.get("income_monthly"):
        payload["income_range"] = financial["income_range"]
    score, rating, recommendation = _score(payload)
    created_at = datetime.now().isoformat(timespec="seconds")
    affiliation_type = payload.get(
        "affiliation_type",
        "Afiliado como trabajador" if payload.get("affiliated") else "No afiliado",
    )
    commercial_summary = (
        f"Busca vivienda en {payload.get('preferred_project', 'proyecto por recomendar')}; "
        f"{payload.get('bedrooms', 'sin dato')} habitaciones; "
        f"horizonte {payload.get('purchase_horizon', 'no informado').lower()}."
    )

    with _connection() as connection:
        id_number = str(payload.get("id_number", "")).strip()
        if id_number:
            previous = connection.execute(
                """
                SELECT lead_code FROM META_LEADS_CAPTURE
                WHERE id_number = ?
                ORDER BY id DESC LIMIT 1
                """,
                (id_number,),
            ).fetchone()
        else:
            previous = connection.execute(
                """
                SELECT lead_code FROM META_LEADS_CAPTURE
                WHERE normalized_name = ?
                ORDER BY id DESC LIMIT 1
                """,
                (normalized_name,),
            ).fetchone()

        cursor = connection.execute(
            """
            INSERT INTO META_LEADS_CAPTURE (
                lead_code, full_name, normalized_name, id_type, income_range,
                affiliated, negative_report, source, campaign, score, rating,
                duplicate_of, crm_status, created_at, id_number, affiliation_type,
                purchase_horizon, savings_range, preferred_project, bedrooms,
                commercial_summary, telegram_username, consent
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                full_name,
                normalized_name,
                payload["id_type"],
                payload["income_range"],
                int(payload["affiliated"]),
                int(payload["negative_report"]),
                payload["source"],
                payload["campaign"],
                score,
                rating,
                previous["lead_code"] if previous else None,
                created_at,
                payload.get("id_number", ""),
                affiliation_type,
                payload.get("purchase_horizon", ""),
                payload.get("savings_range", ""),
                payload.get("preferred_project", ""),
                payload.get("bedrooms"),
                commercial_summary,
                payload.get("telegram_username", ""),
                int(bool(payload.get("consent", False))),
            ),
        )
        lead_code = f"LEAD-{cursor.lastrowid:05d}"
        meta_lead_id = payload.get("meta_lead_id") or f"ML-{uuid.uuid4().hex[:16].upper()}"
        enriched_payload = {
            **payload,
            **financial,
            "full_name": full_name,
            "affiliation_type": affiliation_type,
            "meta_lead_id": meta_lead_id,
            "commercial_summary": commercial_summary,
        }
        crm_payload = _salesforce_payload(
            enriched_payload,
            lead_code,
        )
        connection.execute(
            """
            UPDATE META_LEADS_CAPTURE
            SET lead_code = ?, crm_payload = ?, crm_status = 'PROFILE_PENDING',
                income_monthly = ?, campaign_id = ?, adset_id = ?, ad_id = ?,
                form_id = ?, meta_lead_id = ?, utm_source = ?, utm_medium = ?,
                utm_campaign = ?, utm_content = ?, funnel_status = 'NUEVO',
                colsubsidio_subsidy = ?, concurrent_potential = ?,
                max_monthly_payment = ?
            WHERE id = ?
            """,
            (
                lead_code,
                json.dumps(crm_payload, ensure_ascii=False),
                financial["income_monthly"],
                payload.get("campaign_id", ""),
                payload.get("adset_id", ""),
                payload.get("ad_id", ""),
                payload.get("form_id", ""),
                meta_lead_id,
                payload.get("utm_source", ""),
                payload.get("utm_medium", ""),
                payload.get("utm_campaign", ""),
                payload.get("utm_content", ""),
                financial["colsubsidio_subsidy"],
                financial["concurrent_potential"],
                financial["max_monthly_payment"],
                cursor.lastrowid,
            ),
        )
        _event(
            connection,
            lead_code,
            "META_WEBHOOK",
            "RECEIVED",
            {
                "campaign_id": payload.get("campaign_id", ""),
                "ad_id": payload.get("ad_id", ""),
                "form_id": payload.get("form_id", ""),
                "utm_source": payload.get("utm_source", ""),
            },
        )
        _event(connection, lead_code, "SQLITE_INSERT", "SUCCESS", {"table": "META_LEADS_CAPTURE"})
        _event(
            connection,
            lead_code,
            "SALESFORCE_SYNC",
            "WAITING_PROFILE",
            {"reason": "VIVI debe completar el perfilamiento antes del envío."},
        )

    storage_warning = _sync_full_lead(lead_code)
    return {
        "lead_code": lead_code,
        "score": score,
        "rating": rating,
        "recommendation": recommendation,
        "duplicate": previous is not None,
        "duplicate_of": previous["lead_code"] if previous else None,
        "crm_status": "PROFILE_PENDING",
        "crm_payload": crm_payload,
        "commercial_summary": commercial_summary,
        "meta_lead_id": meta_lead_id,
        "financial_profile": financial,
        "storage_backend": "supabase" if use_supabase() else "sqlite",
        "storage_warning": storage_warning,
    }


def list_leads() -> list[dict[str, Any]]:
    init_db()
    if use_supabase():
        try:
            return fetch_supabase_leads()
        except RuntimeError:
            # Continuidad operativa: la copia local conserva el último estado.
            pass
    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT lead_code, meta_lead_id, full_name, id_type, id_number,
                   income_monthly, income_range,
                   affiliation_type, purchase_horizon, savings_range,
                   preferred_project, bedrooms, score, rating, duplicate_of,
                   crm_status, funnel_status, campaign_id, adset_id, ad_id,
                   form_id, utm_source, utm_medium, utm_campaign, utm_content,
                   colsubsidio_subsidy, concurrent_potential,
                   max_monthly_payment, commercial_summary, created_at,
                   telegram_username, propensity_score, propensity_priority,
                   profile_diagnosis, profile_completed_at
            FROM META_LEADS_CAPTURE ORDER BY id DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def save_conversation_profile(
    lead_code: str,
    profile: dict[str, Any],
    scoring: dict[str, Any],
    diagnosis: str,
) -> str:
    """Persist VIVI's auditable profile and simulate Salesforce only when complete."""
    init_db()
    completed = bool(profile.get("profile_complete"))
    status = "SYNCED" if completed else "PROFILE_PENDING"
    completed_at = datetime.now().isoformat(timespec="seconds") if completed else None
    with _connection() as connection:
        row = connection.execute(
            "SELECT crm_payload FROM META_LEADS_CAPTURE WHERE lead_code = ?",
            (lead_code,),
        ).fetchone()
        if not row:
            raise ValueError(f"No existe el lead {lead_code}.")
        crm_payload = json.loads(row["crm_payload"] or "{}")
        crm_payload.update(
            {
                "Puntaje_Perfilamiento__c": scoring["propensity_score"],
                "Clasificacion_Lead__c": scoring["priority"],
                "Version_Score__c": scoring["score_version"],
                "Razones_Score__c": json.dumps(
                    scoring["score_reasons"], ensure_ascii=False
                ),
                "Desglose_Score__c": json.dumps(
                    scoring["score_breakdown"], ensure_ascii=False
                ),
                "Ruta_Comercial__c": scoring["route"],
                "Ficha_del_Sueno__c": diagnosis,
                "Perfil_Conversacional__c": json.dumps(profile, ensure_ascii=False),
            }
        )
        connection.execute(
            """
            UPDATE META_LEADS_CAPTURE
            SET conversation_profile_json = ?, propensity_score = ?,
                propensity_priority = ?, profile_diagnosis = ?,
                profile_completed_at = ?, crm_payload = ?, crm_status = ?
            WHERE lead_code = ?
            """,
            (
                json.dumps(profile, ensure_ascii=False),
                scoring["propensity_score"],
                scoring["priority"],
                diagnosis,
                completed_at,
                json.dumps(crm_payload, ensure_ascii=False),
                status,
                lead_code,
            ),
        )
        _event(
            connection,
            lead_code,
            "VIVI_PROFILE",
            "COMPLETED" if completed else "UPDATED",
            {"profile": profile, "scoring": scoring, "diagnosis": diagnosis},
        )
        if completed:
            _event(connection, lead_code, "SALESFORCE_SYNC", "SIMULATED", crm_payload)
    if use_supabase():
        try:
            patch_supabase_lead(
                lead_code,
                {
                    "conversation_profile_json": profile,
                    "propensity_score": scoring["propensity_score"],
                    "propensity_priority": scoring["priority"],
                    "profile_diagnosis": diagnosis,
                    "profile_completed_at": completed_at,
                    "crm_payload": crm_payload,
                    "crm_status": status,
                },
            )
            insert_supabase_event(
                lead_code,
                "VIVI_PROFILE",
                "COMPLETED" if completed else "UPDATED",
                {"profile": profile, "scoring": scoring, "diagnosis": diagnosis},
            )
        except RuntimeError as error:
            _register_sync_failure(lead_code, "SAVE_CONVERSATION_PROFILE", error)
    return status


def update_funnel_status(lead_code: str, status: str) -> None:
    allowed = {
        "NUEVO",
        "CONTACTADO",
        "PERFILADO",
        "CITA_AGENDADA",
        "SEPARADO",
        "NUTRICIÓN",
        "DESCARTADO",
    }
    if status not in allowed:
        raise ValueError("Estado comercial no válido.")
    with _connection() as connection:
        cursor = connection.execute(
            "UPDATE META_LEADS_CAPTURE SET funnel_status = ? WHERE lead_code = ?",
            (status, lead_code),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"No existe el lead {lead_code}.")
        _event(connection, lead_code, "SALESFORCE_STAGE", "SIMULATED", {"status": status})
    if use_supabase():
        try:
            patch_supabase_lead(lead_code, {"funnel_status": status})
            insert_supabase_event(
                lead_code,
                "SALESFORCE_STAGE",
                "SIMULATED",
                {"status": status},
            )
        except RuntimeError as error:
            _register_sync_failure(lead_code, "UPDATE_FUNNEL_STATUS", error)


def get_campaign_performance() -> list[dict[str, Any]]:
    init_db()
    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT
                COALESCE(NULLIF(campaign_id, ''), campaign, 'SIN_CAMPAÑA') AS campaign_id,
                COALESCE(NULLIF(preferred_project, ''), 'Sin proyecto') AS project,
                COALESCE(NULLIF(utm_source, ''), source, 'desconocido') AS source,
                COUNT(*) AS records,
                COUNT(DISTINCT normalized_name) AS unique_people,
                SUM(CASE WHEN duplicate_of IS NOT NULL THEN 1 ELSE 0 END) AS duplicates,
                SUM(CASE WHEN rating IN ('ALTA', 'CALIENTE') THEN 1 ELSE 0 END) AS high_priority,
                SUM(CASE WHEN funnel_status = 'SEPARADO' THEN 1 ELSE 0 END) AS separated
            FROM META_LEADS_CAPTURE
            GROUP BY 1, 2, 3
            ORDER BY records DESC
            """
        ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        item["conversion_rate"] = round(
            item["separated"] / item["unique_people"] * 100, 2
        ) if item["unique_people"] else 0.0
        results.append(item)
    return results


def list_events(limit: int = 100) -> list[dict[str, Any]]:
    init_db()
    if use_supabase():
        try:
            return fetch_supabase_events(limit)
        except RuntimeError:
            pass
    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT lead_code, event_type, status, created_at
            FROM INTEGRATION_EVENTS ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_dashboard_metrics() -> dict[str, float | int]:
    init_db()
    if use_supabase():
        try:
            leads = fetch_supabase_leads()
            total = len(leads)
            hot = sum(
                lead.get("rating") in {"ALTA", "CALIENTE"} for lead in leads
            )
            return {
                "total": total,
                "hot": hot,
                "duplicates": sum(
                    bool(lead.get("duplicate_of")) for lead in leads
                ),
                "crm_pending": sum(
                    lead.get("crm_status") != "SYNCED" for lead in leads
                ),
                "conversion_rate": (hot / total * 100) if total else 0.0,
            }
        except RuntimeError:
            pass
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN rating IN ('ALTA', 'CALIENTE') THEN 1 ELSE 0 END) AS hot,
                SUM(CASE WHEN duplicate_of IS NOT NULL THEN 1 ELSE 0 END) AS duplicates,
                SUM(CASE WHEN crm_status != 'SYNCED' THEN 1 ELSE 0 END) AS crm_pending
            FROM META_LEADS_CAPTURE
            """
        ).fetchone()
    total = row["total"] or 0
    hot = row["hot"] or 0
    return {
        "total": total,
        "hot": hot,
        "duplicates": row["duplicates"] or 0,
        "crm_pending": row["crm_pending"] or 0,
        "conversion_rate": (hot / total * 100) if total else 0.0,
    }


def retry_crm_sync() -> int:
    init_db()
    with _connection() as connection:
        pending = connection.execute(
            """
            SELECT lead_code, crm_payload FROM META_LEADS_CAPTURE
            WHERE crm_status != 'SYNCED' AND profile_completed_at IS NOT NULL
            """
        ).fetchall()
        for row in pending:
            connection.execute(
                "UPDATE META_LEADS_CAPTURE SET crm_status = 'SYNCED' WHERE lead_code = ?",
                (row["lead_code"],),
            )
            _event(
                connection,
                row["lead_code"],
                "SALESFORCE_RETRY",
                "SIMULATED",
                json.loads(row["crm_payload"]),
            )
    if use_supabase():
        for row in pending:
            try:
                patch_supabase_lead(row["lead_code"], {"crm_status": "SYNCED"})
                insert_supabase_event(
                    row["lead_code"],
                    "SALESFORCE_RETRY",
                    "SIMULATED",
                    json.loads(row["crm_payload"]),
                )
            except RuntimeError as error:
                _register_sync_failure(row["lead_code"], "RETRY_CRM_SYNC", error)
    return len(pending)
