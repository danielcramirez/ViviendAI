from __future__ import annotations

import json
import os
import re
import unicodedata
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from make_service import load_local_env
from profiling_service import calculate_propensity


APP_DIR = Path(__file__).resolve().parent
CATALOG_PATH = APP_DIR / "config" / "project_catalog.json"
PROFILE_FIELDS = {
    "interest_origin_project",
    "alternative_interest",
    "recommended_projects",
    "preferred_location",
    "purchase_budget",
    "purchase_purpose",
    "lives_in",
    "works_in",
    "household_size",
    "housing_dream",
    "desired_features",
    "accepts_advisor_contact",
    "accepts_appointment",
    "profile_complete",
}


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(
        char for char in text if not unicodedata.combining(char)
    ).casefold()


def load_project_catalog() -> list[dict[str, Any]]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def format_cop(value: int) -> str:
    return f"${value:,.0f}".replace(",", ".")


def extract_budget(message: str) -> int | None:
    normalized = _normalize(message)
    match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(millones?|millon|m)\b",
        normalized,
    )
    if match:
        number = float(match.group(1).replace(",", "."))
        return round(number * 1_000_000)
    digits = re.sub(r"\D", "", message)
    if len(digits) >= 7:
        return int(digits)
    return None


def detect_location(message: str) -> str | None:
    normalized = _normalize(message)
    aliases = {
        "bogota": "Bogotá",
        "chia": "Chía",
        "soacha": "Soacha",
        "ricaurte": "Ricaurte",
        "girardot": "Girardot",
        "tocancipa": "Tocancipá",
        "ubate": "Ubaté",
    }
    for alias, location in aliases.items():
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return location
    return None


def is_catalog_question(message: str) -> bool:
    normalized = _normalize(message)
    terms = (
        "proyecto",
        "proyectos",
        "opciones",
        "viviendas",
        "apartamentos",
        "nombres",
        "precio",
        "presupuesto",
        "en chia",
        "en bogota",
        "en soacha",
    )
    return any(term in normalized for term in terms)


def search_projects(
    location: str | None = None,
    budget: int | None = None,
    housing_type: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    normalized_location = _normalize(location)
    normalized_type = _normalize(housing_type)
    results = []
    for project in load_project_catalog():
        project_location = _normalize(
            f"{project['location']} {project['municipality']}"
        )
        if normalized_location and normalized_location not in project_location:
            continue
        if normalized_type and normalized_type != _normalize(project["type"]):
            continue
        if budget is not None and project["price_from"] > budget:
            continue
        results.append(project)
    return sorted(results, key=lambda item: item["price_from"])[:limit]


def _complete_reply(value: str, maximum: int = 900) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return "No pude completar la respuesta. ¿Quieres que retomemos tu búsqueda?"
    if len(text) <= maximum and text[-1] in ".?!":
        return text
    text = text[:maximum]
    sentence_end = max(text.rfind("."), text.rfind("?"), text.rfind("!"))
    if sentence_end >= 5:
        return text[: sentence_end + 1]
    return text.rstrip(" ,;:-") + "."


def _catalog_reply(
    message: str,
    profile: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    if not is_catalog_question(message):
        return None
    detected_location = detect_location(message)
    location = detected_location or profile.get("preferred_location")
    budget = extract_budget(message) or profile.get("purchase_budget")
    results = search_projects(location=location, budget=budget, limit=5)
    has_budget_match = bool(results)
    if not results and location:
        results = search_projects(location=location, limit=5)
    if not results:
        results = search_projects(limit=5)

    updated = deepcopy(profile)
    if detected_location:
        updated["preferred_location"] = detected_location
    if budget:
        updated["purchase_budget"] = budget
    updated["recommended_projects"] = [item["name"] for item in results[:3]]
    options = "; ".join(
        f"{item['name']} ({item['location']}, desde "
        f"{format_cop(item['price_from'])})"
        for item in results
    )
    if budget and not has_budget_match:
        reply = (
            f"En {location or 'el catálogo'} no encontré una opción desde "
            f"{format_cop(budget)} o menos; las alternativas más cercanas son: "
            f"{options}. ¿Quieres ampliar el presupuesto o revisar otra ubicación?"
        )
    elif not location:
        reply = (
            f"Tenemos estas opciones: {options}. Los precios son aproximados y "
            "deben validarse con un asesor, ¿en qué municipio prefieres comprar?"
        )
    elif budget is None:
        reply = (
            f"En {location} encontré: {options}. Los precios son aproximados, "
            "¿cuál es tu presupuesto máximo?"
        )
    else:
        reply = (
            f"Para {location} y un presupuesto cercano a {format_cop(budget)}, "
            f"encontré: {options}. ¿Cuál opción te interesa más?"
        )
    return _complete_reply(reply), updated


def _system_instruction(catalog: list[dict[str, Any]]) -> str:
    catalog_text = "\n".join(
        f"- {item['name']} | {item['type']} | {item['location']} | "
        f"desde {format_cop(item['price_from'])}"
        for item in catalog
    )
    return f"""Eres VIVI, consultora digital de vivienda de Colsubsidio.
Sé cálida, humana y directa. Responde con máximo 60 palabras, dos frases
completas y una sola pregunta por turno. Nunca termines a mitad de una oración.
No solicites información bancaria, contraseñas, dirección exacta ni centrales
de riesgo. No prometas crédito o subsidio.

Catálogo autorizado:
{catalog_text}

Los precios son aproximados. No inventes proyectos, ubicaciones, áreas,
disponibilidad o precios. Responde primero la pregunta del cliente y después
haz una sola pregunta de perfilamiento. Devuelve exclusivamente JSON válido."""


def _response_schema() -> dict[str, Any]:
    nullable_string = {"type": ["string", "null"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["reply", "profile_updates"],
        "properties": {
            "reply": {"type": "string", "maxLength": 900},
            "profile_updates": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "interest_origin_project": {"type": ["boolean", "null"]},
                    "alternative_interest": nullable_string,
                    "purchase_purpose": nullable_string,
                    "lives_in": nullable_string,
                    "preferred_location": nullable_string,
                    "purchase_budget": {
                        "type": ["integer", "null"],
                        "minimum": 0,
                    },
                    "works_in": nullable_string,
                    "household_size": {
                        "type": ["integer", "string", "null"]
                    },
                    "housing_dream": nullable_string,
                    "desired_features": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 10,
                    },
                    "accepts_advisor_contact": {"type": ["boolean", "null"]},
                    "accepts_appointment": {"type": ["boolean", "null"]},
                },
            },
        },
    }


def _call_gemini(
    message: str,
    history: str,
    profile: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    load_local_env()
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no está configurada.")
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    context = {"message": message, "history": history[-6000:], "profile": profile}
    payload = {
        "systemInstruction": {
            "parts": [{"text": _system_instruction(load_project_catalog())}]
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
            "maxOutputTokens": 900,
            "responseMimeType": "application/json",
            "responseSchema": _response_schema(),
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


def merge_profile(
    profile: dict[str, Any],
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    result = deepcopy(profile)
    for key, value in (updates or {}).items():
        if key in PROFILE_FIELDS and value not in (None, "", []):
            result[key] = value
    return result


def request_agent_reply(
    payload: dict[str, Any],
    timeout: float = 25.0,
) -> dict[str, Any]:
    profile = payload.get("profile")
    if not isinstance(profile, dict):
        raw_profile = payload.get("profile_json", {})
        if isinstance(raw_profile, str):
            try:
                profile = json.loads(raw_profile or "{}")
            except json.JSONDecodeError:
                profile = {}
        else:
            profile = dict(raw_profile or {})
    message = str(payload.get("message") or "").strip()
    history = str(payload.get("history") or "")

    deterministic = _catalog_reply(message, profile)
    if deterministic:
        reply, updated = deterministic
        source = "CATALOGO_DETERMINISTICO"
        warning = None
    else:
        try:
            generated = _call_gemini(message, history, profile, timeout)
            reply = _complete_reply(generated.get("reply", ""))
            updated = merge_profile(profile, generated.get("profile_updates"))
            source = "GEMINI_API_DIRECTA"
            warning = None
        except RuntimeError as error:
            from instagram_simulator import process_message

            reply, updated = process_message(message, profile)
            reply = _complete_reply(reply)
            source = "SIMULADOR_LOCAL"
            warning = str(error)

    scoring = calculate_propensity(updated)
    updated["propensity_score"] = scoring["propensity_score"]
    updated["propensity_priority"] = scoring["priority"]
    updated["score_version"] = scoring["score_version"]
    updated["missing_fields"] = scoring["missing_fields"]
    updated["agent_source"] = source
    updated["integration_warning"] = warning
    return {
        "ok": True,
        "reply": reply,
        "profile": updated,
        "scoring": scoring,
        "source": source,
        "warning": warning,
    }
