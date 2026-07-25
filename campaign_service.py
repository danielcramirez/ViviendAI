from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

from catalog_service import get_project_names


PLACEMENTS = {
    "Instagram": ("instagram", "paid_social"),
    "Facebook": ("facebook", "paid_social"),
    "WhatsApp": ("whatsapp", "messaging"),
    "Landing orgánica": ("google", "organic"),
}


def _slug(value: str) -> str:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def build_attribution(project: str, placement: str = "Instagram") -> dict[str, str]:
    if placement not in PLACEMENTS:
        raise ValueError(f"Origen no soportado: {placement}")
    utm_source, utm_medium = PLACEMENTS[placement]
    project_slug = _slug(project)
    campaign_key = f"vivienda-{project_slug}-2026"
    return {
        "project": project,
        "placement": placement,
        "campaign_id": _stable_id("CMP", campaign_key),
        "campaign_name": campaign_key,
        "adset_id": _stable_id("SET", f"{campaign_key}-{placement}"),
        "ad_id": _stable_id("AD", f"{campaign_key}-{placement}-sueno-vivienda"),
        "form_id": _stable_id("FORM", f"{project_slug}-perfilamiento"),
        "utm_source": utm_source,
        "utm_medium": utm_medium,
        "utm_campaign": campaign_key,
        "utm_content": "sueno-vivienda-v1",
    }


def list_campaigns() -> list[dict[str, Any]]:
    return [build_attribution(project) for project in get_project_names()]
