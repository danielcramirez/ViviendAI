from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from make_service import load_local_env


JSON_FIELDS = {
    "crm_payload",
    "conversation_profile_json",
}
BOOLEAN_FIELDS = {
    "affiliated",
    "negative_report",
    "consent",
}


def _settings() -> tuple[str, str]:
    load_local_env()
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()
    return url, key


def is_configured() -> bool:
    url, key = _settings()
    return bool(
        url.startswith("https://")
        and key
        and "REEMPLAZAR" not in key
        and "ROTAR_" not in key
    )


def use_supabase() -> bool:
    load_local_env()
    return (
        os.getenv("DATA_BACKEND", "sqlite").strip().casefold() == "supabase"
        and is_configured()
    )


def _request(
    table: str,
    *,
    method: str = "GET",
    params: dict[str, str] | None = None,
    payload: Any = None,
    prefer: str | None = None,
    timeout: float = 20.0,
) -> Any:
    url, key = _settings()
    if not is_configured():
        raise RuntimeError("Supabase no está configurado con una clave secreta válida.")
    endpoint = f"{url}/rest/v1/{table}"
    if params:
        endpoint += "?" + urlencode(params, safe="(),.*:")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    data = (
        json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        if payload is not None
        else None
    )
    request = Request(endpoint, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Supabase respondió HTTP {error.code}: {detail[:500]}"
        ) from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"No fue posible contactar Supabase: {error}") from error
    return json.loads(body) if body else None


def normalize_lead(row: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in row.items() if key != "id"}
    for field in BOOLEAN_FIELDS:
        if field in result and result[field] is not None:
            result[field] = bool(result[field])
    for field in JSON_FIELDS:
        value = result.get(field)
        if isinstance(value, str):
            try:
                result[field] = json.loads(value or "{}")
            except json.JSONDecodeError:
                result[field] = {"raw": value}
    return result


def upsert_lead(row: dict[str, Any]) -> None:
    payload = normalize_lead(row)
    _request(
        "vivi_leads",
        method="POST",
        params={"on_conflict": "lead_code"},
        payload=payload,
        prefer="resolution=merge-duplicates,return=minimal",
    )


def insert_event(
    lead_code: str,
    event_type: str,
    status: str,
    details: Any,
    created_at: str | None = None,
) -> None:
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except json.JSONDecodeError:
            details = {"message": details}
    _request(
        "vivi_integration_events",
        method="POST",
        payload={
            "lead_code": lead_code,
            "event_type": event_type,
            "status": status,
            "details": details or {},
            "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
        },
        prefer="return=minimal",
    )


def fetch_leads() -> list[dict[str, Any]]:
    rows = _request(
        "vivi_leads",
        params={"select": "*", "order": "created_at.desc"},
    )
    return list(rows or [])


def fetch_events(limit: int = 100) -> list[dict[str, Any]]:
    rows = _request(
        "vivi_integration_events",
        params={
            "select": "lead_code,event_type,status,created_at",
            "order": "created_at.desc",
            "limit": str(max(1, min(limit, 1000))),
        },
    )
    return list(rows or [])


def patch_lead(lead_code: str, values: dict[str, Any]) -> None:
    payload = normalize_lead(values)
    _request(
        "vivi_leads",
        method="PATCH",
        params={"lead_code": f"eq.{lead_code}"},
        payload=payload,
        prefer="return=minimal",
    )
