from __future__ import annotations

from typing import Any


SMMLV_2026 = 1_750_905
SUBSIDY_30 = 30 * SMMLV_2026
SUBSIDY_20 = 20 * SMMLV_2026
CONCURRENT_POTENTIAL = 20 * SMMLV_2026


def income_range_for(income_monthly: int) -> str:
    if income_monthly <= 2 * SMMLV_2026:
        return "Hasta 2 SMMLV"
    if income_monthly <= 4 * SMMLV_2026:
        return "Entre 2 y 4 SMMLV"
    return "Más de 4 SMMLV"


def calculate_financial_profile(
    income_monthly: int,
    affiliation_type: str,
) -> dict[str, Any]:
    income = max(0, int(income_monthly))
    affiliated = affiliation_type in {"Afiliado como trabajador", "Beneficiario"}
    range_name = income_range_for(income)

    subsidy = 0
    if affiliated and income <= 2 * SMMLV_2026:
        subsidy = SUBSIDY_30
    elif affiliated and income <= 4 * SMMLV_2026:
        subsidy = SUBSIDY_20

    concurrent = (
        CONCURRENT_POTENTIAL
        if affiliated and 0 < income < 2 * SMMLV_2026
        else 0
    )
    return {
        "income_monthly": income,
        "income_range": range_name,
        "smmlv_ratio": round(income / SMMLV_2026, 2) if income else 0,
        "colsubsidio_subsidy": subsidy,
        "concurrent_potential": concurrent,
        "total_potential": subsidy + concurrent,
        "max_monthly_payment": round(income * 0.40),
        "eligible_by_income": affiliated and 0 < income <= 4 * SMMLV_2026,
        "disclaimer": (
            "Estimación orientativa. La asignación exige validar afiliación, antigüedad, "
            "hogar, aportes y requisitos vigentes. Mi Casa Ya requiere validación externa."
        ),
    }
