from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any


APP_DIR = Path(__file__).resolve().parent
CATALOG_PATH = APP_DIR / "tableConvert.com_x950qq.json"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _parse_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%m/%d/%y")
    except (TypeError, ValueError):
        return None


def _parse_price(value: str) -> int | None:
    try:
        raw_value = int(_clean(value).replace(",", ""))
    except ValueError:
        return None
    # El archivo exportado contiene cuatro ceros adicionales en los valores
    # monetarios. Se conserva como una estimación analítica, no como precio oficial.
    return round(raw_value / 10_000)


def _top(counter: Counter[str], limit: int = 3) -> list[dict[str, int | str]]:
    return [
        {"label": label, "count": count}
        for label, count in counter.most_common(limit)
        if label
    ]


def load_catalog(path: Path = CATALOG_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    records = json.loads(path.read_text(encoding="utf-8-sig"))
    projects: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        name = _clean(row.get("NOMBRE_PROYECTO"))
        if name:
            projects.setdefault(name, []).append(row)

    catalog: list[dict[str, Any]] = []
    for name, rows in projects.items():
        dates = [
            parsed
            for parsed in (_parse_date(_clean(row.get("FEC_OPCION"))) for row in rows)
            if parsed
        ]
        prices = [
            parsed
            for parsed in (_parse_price(_clean(row.get("VLR_VIVIENDA"))) for row in rows)
            if parsed and parsed > 0
        ]
        stages = sorted({_clean(row.get("ETAPA")) for row in rows if _clean(row.get("ETAPA"))})
        desistments = sum(
            1
            for row in rows
            if _clean(row.get("FECHA_DESISTIMIENTO")).casefold() not in {"", "no"}
        )

        catalog.append(
            {
                "name": name,
                "records": len(rows),
                "stages": stages,
                "first_option": min(dates).date().isoformat() if dates else None,
                "last_option": max(dates).date().isoformat() if dates else None,
                "estimated_price_median": round(median(prices)) if prices else None,
                "estimated_price_min": min(prices) if prices else None,
                "estimated_price_max": max(prices) if prices else None,
                "desistments": desistments,
                "desistment_rate": round(desistments / len(rows) * 100, 1),
                "age_ranges": _top(Counter(_clean(row.get("RANGO_EDAD")) for row in rows)),
                "channels": _top(Counter(_clean(row.get("MEDIO")) for row in rows)),
                "financial_entities": _top(
                    Counter(_clean(row.get("Entidad Financiera compra")) for row in rows)
                ),
                "population_segments": _top(
                    Counter(_clean(row.get("SEGMENTO_POBLACIONAL")) for row in rows)
                ),
            }
        )

    return sorted(catalog, key=lambda project: (-project["records"], project["name"]))


def get_project_names() -> list[str]:
    return [project["name"] for project in load_catalog()]
