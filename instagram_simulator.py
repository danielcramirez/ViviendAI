from __future__ import annotations

import re
from typing import Any


def start_conversation(full_name: str, project: str) -> list[dict[str, str]]:
    first_name = full_name.strip().split()[0]
    return [
        {
            "role": "assistant",
            "content": (
                f"¡Hola, {first_name}! Soy VIVI, tu consultora virtual de vivienda. "
                f"Vi que conociste el proyecto "
                f"{project} por nuestra campaña de Instagram. "
                "¿Sigue siendo tu opción principal o prefieres explorar otro proyecto?"
            ),
        }
    ]


def empty_profile(
    project: str,
    campaign_id: str,
    lead_code: str,
    form_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = form_context or {}
    return {
        "lead_code": lead_code,
        "customer_name": context.get("full_name"),
        "channel": "INSTAGRAM_SIMULADO",
        "campaign_id": campaign_id,
        "project_origin": project,
        "interest_origin_project": None,
        "alternative_interest": None,
        "purchase_purpose": None,
        "lives_in": None,
        "preferred_location": None,
        "works_in": None,
        "household_size": None,
        "housing_dream": None,
        "desired_features": [],
        "purchase_horizon": context.get("purchase_horizon"),
        "savings_range": context.get("savings_range"),
        "household_income": context.get("income_monthly"),
        "purchase_budget": None,
        "affiliation_type": context.get("affiliation_type"),
        "bedrooms": context.get("bedrooms"),
        "max_monthly_payment": context.get("max_monthly_payment", 0),
        "consent": bool(context.get("consent", False)),
        "accepts_advisor_contact": None,
        "accepts_appointment": None,
        "profile_complete": False,
    }


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _words(value: str) -> set[str]:
    return set(re.findall(r"\b[\wáéíóúüñ]+\b", value.casefold()))


def process_message(message: str, profile: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    text = _clean(message)
    normalized = text.casefold()
    words = _words(text)
    updated = dict(profile)

    if updated["interest_origin_project"] is None:
        negative = bool(words.intersection({"no", "otro", "otra", "alternativa", "alternativas"}))
        updated["interest_origin_project"] = not negative
        if negative:
            updated["alternative_interest"] = text
            reply = (
                "Perfecto, podemos explorar alternativas sin compromiso. "
                "¿Buscas la vivienda para vivir, invertir o para un familiar?"
            )
        else:
            reply = (
                f"Excelente, continuemos con {updated['project_origin']}. "
                "¿Buscas la vivienda para vivir, invertir o para un familiar?"
            )
    elif not updated["purchase_purpose"]:
        updated["purchase_purpose"] = text
        reply = "Para recomendarte mejor, ¿en qué ciudad o sector vives actualmente?"
    elif not updated["lives_in"]:
        updated["lives_in"] = text
        reply = "Gracias. ¿En qué ciudad o sector trabajas o realizas la mayor parte de tus actividades?"
    elif not updated["works_in"]:
        updated["works_in"] = text
        reply = "¿Cuántas personas vivirían en la nueva vivienda?"
    elif not updated["household_size"]:
        match = re.search(r"\d+", text)
        updated["household_size"] = int(match.group()) if match else text
        reply = (
            "Eso me ayuda a considerar tus desplazamientos. "
            "¿Qué sería indispensable en tu vivienda ideal, por ejemplo balcón, zonas verdes o más habitaciones?"
        )
    elif not updated["housing_dream"]:
        updated["housing_dream"] = text
        updated["desired_features"] = [
            item.strip() for item in re.split(r",| y ", text) if item.strip()
        ][:10]
        reply = (
            "Ya tengo lo esencial de tu Ficha del Sueño. "
            "¿Autorizas que un asesor te contacte para revisar opciones o agendar una visita?"
        )
    elif updated["accepts_advisor_contact"] is None:
        positive = bool(words.intersection({"sí", "si", "claro", "acepto", "visita"}))
        updated["accepts_advisor_contact"] = positive
        updated["accepts_appointment"] = positive and "visita" in normalized
        updated["profile_complete"] = True
        reply = (
            "¡Gracias! Tu Ficha del Sueño quedó lista para el equipo comercial. "
            "Conservaremos el contexto para que no tengas que repetir la conversación."
            if positive
            else "Entendido. Guardaré tu perfil sin solicitar contacto comercial adicional."
        )
    else:
        reply = (
            "He añadido tu respuesta al contexto del proceso. "
            "¿Hay algo más que quieras que el asesor conozca antes de contactarte?"
        )

    return reply, updated
