from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from make_service import load_local_env
from profiling_service import build_diagnosis, calculate_propensity
from lead_service import save_conversation_profile
from vivi_agent_service import load_project_catalog, format_cop


APP_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = APP_DIR / "schemas" / "lead_profile.schema.json"

# Fields that Agent 2 can extract from conversation history.
# Drawn from lead_profile.schema.json — excludes fields that come from
# form/campaign attribution (lead_code, campaign_id, project_origin, etc.).
EXTRACTABLE_FIELDS = frozenset({
    "interest_origin_project",
    "alternative_interest",
    "recommended_projects",
    "preferred_location",
    "purchase_purpose",
    "lives_in",
    "works_in",
    "household_size",
    "housing_dream",
    "desired_features",
    "purchase_budget",
    "purchase_horizon",
    "savings_range",
    "accepts_advisor_contact",
    "accepts_appointment",
    "profile_complete",
})


def _load_schema() -> dict[str, Any]:
    """Load the lead profile JSON Schema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# Map from JSON Schema type names to Python types for validation.
_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "array": list,
    "number": (int, float),
}


def _validate_against_schema(
    data: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    """Inline JSON Schema validation without adding a jsonschema dependency.

    Checks required fields, type constraints, enums, maxLength, pattern,
    minimum, maximum, and additionalProperties for the lead profile schema.
    Returns a list of human-readable validation errors.
    """
    errors: list[str] = []
    required = set(schema.get("required", []))
    props = schema.get("properties", {})

    # --- additionalProperties: false ---
    allowed = set(props.keys())
    for key in data:
        if key not in allowed:
            errors.append(f"Campo no permitido: '{key}'")

    # --- required ---
    for field in required:
        if field not in data or data[field] is None:
            errors.append(f"Campo requerido ausente o nulo: '{field}'")

    # --- per-field checks ---
    for field, value in data.items():
        if field not in props:
            continue
        definition = props[field]
        if value is None:
            nullable = isinstance(definition.get("type"), list) and "null" in definition["type"]
            if not nullable and field in required:
                errors.append(f"Campo '{field}' es requerido pero es null")
            continue

        type_spec = definition.get("type", [])
        allowed_types: list[str] = (
            list(type_spec) if isinstance(type_spec, list) else [type_spec]
        )

        # Type checks — convert JSON Schema type names to Python types
        value_type = type(value).__name__
        if "string" in allowed_types and not isinstance(value, str):
            pass
        elif isinstance(value, str) and "string" not in allowed_types and "integer" not in allowed_types:
            python_types = tuple(
                _TYPE_MAP[t] for t in allowed_types if t in _TYPE_MAP
            )
            if python_types and not isinstance(value, python_types):
                errors.append(f"Campo '{field}': se esperaba {allowed_types}, se obtuvo {value_type}")

        # Enum check
        enum_vals = definition.get("enum")
        if enum_vals is not None and value not in enum_vals:
            errors.append(f"Campo '{field}': valor '{value}' no está en {enum_vals}")

        # maxLength
        max_len = definition.get("maxLength")
        if max_len is not None and isinstance(value, str) and len(value) > max_len:
            errors.append(f"Campo '{field}' excede {max_len} caracteres ({len(value)})")

        # pattern
        pattern = definition.get("pattern")
        if pattern is not None and isinstance(value, str) and not re.search(pattern, value):
            errors.append(f"Campo '{field}' no coincide con el patrón {pattern}")

        # minimum / maximum
        min_val = definition.get("minimum")
        max_val = definition.get("maximum")
        if isinstance(value, (int, float)):
            if min_val is not None and value < min_val:
                errors.append(f"Campo '{field}'={value} es menor que mínimo {min_val}")
            if max_val is not None and value > max_val:
                errors.append(f"Campo '{field}'={value} es mayor que máximo {max_val}")

        # maxItems for arrays
        max_items = definition.get("maxItems")
        if max_items is not None and isinstance(value, list) and len(value) > max_items:
            errors.append(f"Campo '{field}' excede {max_items} elementos ({len(value)})")

    return errors


def _system_instruction() -> str:
    """System prompt for Agent 2's structured extraction call."""
    catalog = load_project_catalog()
    catalog_text = "\n".join(
        f"- {item['name']} | {item['type']} | {item['location']} | "
        f"desde {format_cop(item['price_from'])}"
        for item in catalog
    )
    return (
        "Eres el Analista de Perfilamiento de VIVI, un extractor estructurado de datos de vivienda.\n\n"
        "Recibes el historial completo de una conversación entre VIVI (consultora) y un cliente "
        "potencial de Colsubsidio. Tu tarea es extraer ÚNICAMENTE la información que el cliente "
        "ha expresado explícitamente o que se puede inferir razonablemente de sus respuestas.\n\n"
        "REGLAS ESTRICTAS:\n"
        "1. NO inventes valores. Si el cliente no ha mencionado un campo, devuélvelo como null.\n"
        "2. NO uses información que no esté en el historial de conversación.\n"
        "3. Para campos booleanos (interest_origin_project, accepts_advisor_contact, \n"
        "   accepts_appointment, profile_complete), solo asigna true si el cliente dijo "
        "explícitamente que sí. Si dijo que no, asigna false. Si no lo mencionó, null.\n"
        "4. Para recommended_projects, solo incluye proyectos del catálogo autorizado que\n"
        "   el cliente haya mencionado o que se ajusten a sus preferencias declaradas.\n"
        "5. Para desired_features, lista las características que el cliente mencionó\n"
        "   (parques, alcobas, balcón, etc.). Vacío si no mencionó ninguna.\n"
        "6. Para housing_dream, captura textualmente cómo describió su vivienda ideal.\n"
        "7. Para purchase_purpose, captura el motivo (crecer familiar, independizarse, invertir, etc.).\n"
        "8. Para purchase_horizon, usa exactamente uno de: \"En los próximos 6 meses\",\n"
        "   \"Entre 6 y 12 meses\", \"En más de 12 meses\", \"Estoy explorando\", o null.\n"
        "9. Para savings_range, usa exactamente uno de: \"Aún no tengo ahorro\",\n"
        "   \"Menos de $3 millones\", \"Entre $3 y $10 millones\", \"Más de $10 millones\",\n"
        "   \"Prefiero no responder\", o null.\n"
        "10. profile_complete debe ser true SOLO si al menos 6 de los campos de\n"
        "    perfilamiento tienen valor (excluyendo lead_code, campaign_id, etc.).\n\n"
        "Catálogo autorizado de proyectos:\n"
        f"{catalog_text}\n\n"
        "Los precios son aproximados. No inventes proyectos, ubicaciones, áreas ni precios.\n"
        "Devuelve exclusivamente JSON válido con los campos extraídos."
    )


def _extraction_schema() -> dict[str, Any]:
    """Response schema for Gemini extraction — mirrors lead_profile.schema.json fields."""
    nullable_str = {"type": ["string", "null"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "interest_origin_project": {"type": ["boolean", "null"]},
            "alternative_interest": nullable_str,
            "recommended_projects": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 3,
            },
            "preferred_location": nullable_str,
            "purchase_purpose": nullable_str,
            "lives_in": nullable_str,
            "works_in": nullable_str,
            "household_size": {"type": ["integer", "string", "null"]},
            "housing_dream": nullable_str,
            "desired_features": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 10,
            },
            "purchase_budget": {"type": ["integer", "null"], "minimum": 0},
            "purchase_horizon": {
                "type": ["string", "null"],
                "enum": [
                    "En los próximos 6 meses",
                    "Entre 6 y 12 meses",
                    "En más de 12 meses",
                    "Estoy explorando",
                ],
            },
            "savings_range": {
                "type": ["string", "null"],
                "enum": [
                    "Aún no tengo ahorro",
                    "Menos de $3 millones",
                    "Entre $3 y $10 millones",
                    "Más de $10 millones",
                    "Prefiero no responder",
                ],
            },
            "accepts_advisor_contact": {"type": ["boolean", "null"]},
            "accepts_appointment": {"type": ["boolean", "null"]},
            "profile_complete": {"type": ["boolean", "null"]},
        },
    }


def _call_gemini_extraction(
    history: str,
    current_profile: dict[str, Any],
    timeout: float = 25.0,
) -> dict[str, Any]:
    """Call Gemini with the structured extraction prompt for Agent 2."""
    load_local_env()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no está configurada.")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )

    context = {
        "conversation_history": history[-8000:],
        "current_profile": {
            k: v for k, v in current_profile.items()
            if k in EXTRACTABLE_FIELDS and v not in (None, "", [], {})
        },
    }
    payload = {
        "systemInstruction": {
            "parts": [{"text": _system_instruction()}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": json.dumps(
                            context,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    }
                ],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 1200,
            "responseMimeType": "application/json",
            "responseSchema": _extraction_schema(),
        },
    }
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Gemini respondió HTTP {error.code}: {detail[:300]}"
        ) from error
    except (URLError, TimeoutError) as error:
        raise RuntimeError(f"No fue posible contactar Gemini: {error}") from error
    try:
        text = raw["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Gemini no devolvió el contrato JSON esperado."
        ) from error


def _merge_extracted_profile(
    profile: dict[str, Any],
    extracted: dict[str, Any],
) -> dict[str, Any]:
    """Merge extracted fields into the current profile.

    Only updates fields from EXTRACTABLE_FIELDS with non-None values.
    Preserves existing values when extraction returns None for that field.
    """
    result = deepcopy(profile)
    for key in EXTRACTABLE_FIELDS:
        value = extracted.get(key)
        if value not in (None, "", [], {}):
            result[key] = value
    return result


def _count_profile_fields(profile: dict[str, Any]) -> int:
    """Count how many extractable fields have meaningful values."""
    return sum(
        1 for key in EXTRACTABLE_FIELDS
        if profile.get(key) not in (None, "", [], {})
    )


def analyze_profile(
    lead_id: str,
    channel: str,
    customer_name: str | None,
    project_origin: str,
    campaign_id: str,
    history: str,
    profile: dict[str, Any] | str,
    force: bool = False,
    timeout: float = 25.0,
) -> dict[str, Any]:
    """Execute Agent 2's full analysis pipeline.

    Args:
        lead_id: Unique lead code (LEAD-xxxxx).
        channel: Communication channel (telegram, instagram, etc.).
        customer_name: Customer's name if known.
        project_origin: Project that originated the lead.
        campaign_id: Campaign identifier.
        history: Full conversation history as text.
        profile: Current profile dict or JSON string.
        force: If True, run extraction even if profile looks sparse.
        timeout: Gemini API timeout in seconds.

    Returns:
        Dict with keys: ok, reply_warning, profile, scoring, diagnosis,
        validation_errors, gemini_source, crm_status.
    """
    # Parse profile
    if isinstance(profile, str):
        try:
            parsed = json.loads(profile or "{}")
        except json.JSONDecodeError:
            parsed = {}
    else:
        parsed = dict(profile or {})

    # Ensure attribution fields are present
    parsed.setdefault("lead_code", lead_id)
    parsed.setdefault("channel", channel)
    parsed.setdefault("customer_name", customer_name)
    parsed.setdefault("project_origin", project_origin)
    parsed.setdefault("campaign_id", campaign_id)
    parsed.setdefault("consent", True)

    # Determine if analysis is needed
    filled_count = _count_profile_fields(parsed)
    if not force and filled_count < 2 and not history.strip():
        # Not enough conversation to analyze
        scoring = calculate_propensity(parsed)
        diagnosis = build_diagnosis(parsed, scoring)
        return {
            "ok": True,
            "reply_warning": "No hay suficiente conversación para perfilamiento estructurado.",
            "profile": parsed,
            "scoring": scoring,
            "diagnosis": diagnosis,
            "schema_errors": [],
            "gemini_source": None,
            "crm_status": "PROFILE_PENDING",
        }

    # Step 1: Call Gemini for structured extraction (if there's history)
    gemini_source = None
    schema_errors: list[str] = []
    extraction_warning: str | None = None

    if history.strip():
        try:
            extracted = _call_gemini_extraction(history, parsed, timeout)
            gemini_source = "GEMINI_AGENTE2"
        except RuntimeError as error:
            extracted = {}
            gemini_source = "FALLBACK_SIN_EXTRACCION"
            extraction_warning = str(error)

        # Step 2: Merge extracted data
        if extracted:
            parsed = _merge_extracted_profile(parsed, extracted)

            # Step 3: Validate against JSON Schema
            schema = _load_schema()
            schema_errors = _validate_against_schema(parsed, schema)
    else:
        gemini_source = "SIN_HISTORIAL"
        extraction_warning = "No hay historial de conversación para extraer datos."

    # Auto-determine profile_complete if not set
    filled = _count_profile_fields(parsed)
    if parsed.get("profile_complete") is None and filled >= 6:
        parsed["profile_complete"] = True

    # Step 4: Run deterministic scoring
    scoring = calculate_propensity(parsed)
    parsed["propensity_score"] = scoring["propensity_score"]
    parsed["propensity_priority"] = scoring["priority"]
    parsed["score_version"] = scoring["score_version"]
    parsed["missing_fields"] = scoring["missing_fields"]
    parsed["agent_source"] = gemini_source
    if extraction_warning:
        parsed["extraction_warning"] = extraction_warning

    # Step 5: Build diagnosis
    diagnosis = build_diagnosis(parsed, scoring)
    parsed["diagnosis"] = diagnosis

    # Step 6: Persist
    try:
        crm_status = save_conversation_profile(lead_id, parsed, scoring, diagnosis)
    except (ValueError, RuntimeError) as error:
        crm_status = "ERROR"
        extraction_warning = (extraction_warning or "") + f" Persistencia: {error}"

    return {
        "ok": True,
        "reply_warning": extraction_warning,
        "profile": parsed,
        "scoring": scoring,
        "diagnosis": diagnosis,
        "schema_errors": schema_errors,
        "gemini_source": gemini_source,
        "crm_status": crm_status,
    }
