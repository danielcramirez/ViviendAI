from __future__ import annotations

from typing import Any


VERSION = "VIVI-1.0"


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def calculate_propensity(profile: dict[str, Any]) -> dict[str, Any]:
    breakdown: dict[str, int] = {}
    reasons: list[str] = []

    intent = 0
    if profile.get("interest_origin_project") is True:
        intent += 12
        reasons.append("Confirma interés en el proyecto de origen (+12)")
    elif profile.get("alternative_interest"):
        intent += 6
        reasons.append("Acepta explorar un proyecto alternativo (+6)")
    if _present(profile.get("purchase_purpose")):
        intent += 5
        reasons.append("Expresa un propósito concreto de compra (+5)")
    if _present(profile.get("housing_dream")):
        intent += 4
        reasons.append("Describe necesidades de vivienda (+4)")
    if profile.get("accepts_advisor_contact") is True:
        intent += 4
        reasons.append("Autoriza contacto de un asesor (+4)")
    breakdown["intent"] = min(intent, 25)

    horizon_map = {
        "En los próximos 6 meses": 15,
        "Entre 6 y 12 meses": 10,
        "En más de 12 meses": 5,
        "Estoy explorando": 2,
    }
    breakdown["horizon"] = horizon_map.get(profile.get("purchase_horizon"), 0)
    if breakdown["horizon"]:
        reasons.append(f"Horizonte de compra declarado (+{breakdown['horizon']})")

    financial = 0
    if (profile.get("household_income") or 0) > 0:
        financial += 8
        reasons.append("Declara ingresos del hogar (+8)")
    savings_map = {
        "Más de $10 millones": 10,
        "Entre $3 y $10 millones": 7,
        "Menos de $3 millones": 3,
        "Aún no tengo ahorro": 0,
        "Prefiero no responder": 0,
    }
    savings_points = savings_map.get(profile.get("savings_range"), 0)
    financial += savings_points
    if savings_points:
        reasons.append(f"Declara ahorro para cuota inicial (+{savings_points})")
    if (profile.get("max_monthly_payment") or 0) > 0:
        financial += 4
        reasons.append("Cuenta con cuota máxima orientativa calculada (+4)")
    if _present(profile.get("affiliation_type")):
        financial += 3
        reasons.append("Afiliación declarada y verificable (+3)")
    breakdown["financial_readiness"] = min(financial, 25)

    project_fit = 0
    if profile.get("interest_origin_project") is True:
        project_fit += 7
    elif profile.get("alternative_interest"):
        project_fit += 4
    if _present(profile.get("lives_in")) and _present(profile.get("works_in")):
        project_fit += 4
        reasons.append("Permite evaluar ubicación y desplazamientos (+4)")
    if _present(profile.get("desired_features")):
        project_fit += 4
        reasons.append("Define características para recomendar proyecto (+4)")
    breakdown["project_fit"] = min(project_fit, 15)

    engagement_fields = (
        "purchase_purpose",
        "lives_in",
        "works_in",
        "household_size",
        "housing_dream",
    )
    answered = sum(_present(profile.get(field)) for field in engagement_fields)
    breakdown["engagement"] = min(answered * 2, 10)
    if answered:
        reasons.append(f"Completó {answered} datos conversacionales (+{breakdown['engagement']})")

    next_step = 0
    if profile.get("accepts_advisor_contact") is True:
        next_step += 5
    if profile.get("accepts_appointment") is True:
        next_step += 5
    breakdown["next_step"] = next_step
    if next_step:
        reasons.append(f"Acepta un siguiente paso comercial (+{next_step})")

    total = min(sum(breakdown.values()), 100)
    conversation_started = (
        profile.get("interest_origin_project") is not None
        or any(
            _present(profile.get(field))
            for field in (
                "purchase_purpose",
                "lives_in",
                "works_in",
                "household_size",
                "housing_dream",
            )
        )
    )
    if not conversation_started:
        priority, route = "EN PERFILAMIENTO", "VIVI"
        action = "Continuar la conversación antes de determinar la prioridad comercial."
    elif total >= 80:
        priority, route = "ALTA", "ASESOR_COMERCIAL"
        action = "Asignar asesor y contactar con la Ficha del Sueño."
    elif total >= 55:
        priority, route = "MEDIA", "COMPLETAR_PERFIL"
        action = "Completar datos faltantes y ofrecer simulación o visita."
    elif total >= 30:
        priority, route = "NUTRICIÓN", "PERTENECER"
        action = "Mantener acompañamiento y recomendar alternativas."
    else:
        priority, route = "TEMPRANO", "NUTRICIÓN_DIGITAL"
        action = "Continuar conversación sin presión comercial."

    required = {
        "interest_origin_project": "interés en el proyecto",
        "purchase_purpose": "propósito de compra",
        "lives_in": "zona donde vive",
        "works_in": "zona donde trabaja",
        "household_size": "personas que vivirían en el inmueble",
        "housing_dream": "características deseadas",
        "accepts_advisor_contact": "autorización de contacto",
    }
    missing = [label for field, label in required.items() if not _present(profile.get(field))]
    return {
        "score_version": VERSION,
        "propensity_score": total,
        "priority": priority,
        "route": route,
        "score_breakdown": breakdown,
        "score_reasons": reasons,
        "missing_fields": missing,
        "recommended_action": action,
        "disclaimer": "Prioridad comercial; no equivale a aprobación de crédito o subsidio.",
    }


def build_diagnosis(profile: dict[str, Any], scoring: dict[str, Any]) -> str:
    if profile.get("interest_origin_project") is True:
        interest = f"mantiene interés en {profile.get('project_origin')}"
    elif profile.get("interest_origin_project") is False:
        interest = "está abierto a proyectos alternativos"
    else:
        interest = "aún debe confirmar su interés en el proyecto de origen"
    context = []
    if profile.get("lives_in"):
        context.append(f"vive en {profile['lives_in']}")
    if profile.get("works_in"):
        context.append(f"trabaja o desarrolla actividades en {profile['works_in']}")
    if profile.get("housing_dream"):
        context.append(f"busca {profile['housing_dream']}")
    detail = "; ".join(context) if context else "aún tiene información conversacional pendiente"
    return (
        f"Lead que {interest}; {detail}. "
        f"Propensión {scoring['propensity_score']}/100 ({scoring['priority']}). "
        f"{scoring['recommended_action']}"
    )
