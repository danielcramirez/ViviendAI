import unittest

from profiling_service import build_diagnosis, calculate_propensity


class ProfilingServiceTests(unittest.TestCase):
    def test_complete_ready_profile_routes_to_advisor(self):
        profile = {
            "project_origin": "Araucaria",
            "interest_origin_project": True,
            "alternative_interest": None,
            "purchase_purpose": "Vivir con mi familia",
            "lives_in": "Suba",
            "works_in": "Calle 80",
            "household_size": 4,
            "housing_dream": "Tres habitaciones y zonas verdes",
            "desired_features": ["Tres habitaciones", "zonas verdes"],
            "purchase_horizon": "En los próximos 6 meses",
            "household_income": 5_000_000,
            "savings_range": "Más de $10 millones",
            "max_monthly_payment": 2_000_000,
            "affiliation_type": "Afiliado como trabajador",
            "accepts_advisor_contact": True,
            "accepts_appointment": True,
        }
        scoring = calculate_propensity(profile)
        self.assertEqual(scoring["propensity_score"], 100)
        self.assertEqual(scoring["priority"], "ALTA")
        self.assertEqual(scoring["route"], "ASESOR_COMERCIAL")
        self.assertIn("Araucaria", build_diagnosis(profile, scoring))

    def test_score_is_explainable_and_capped(self):
        scoring = calculate_propensity({})
        self.assertEqual(scoring["propensity_score"], 0)
        self.assertEqual(scoring["priority"], "EN PERFILAMIENTO")
        self.assertEqual(scoring["route"], "VIVI")
        self.assertEqual(sum(scoring["score_breakdown"].values()), 0)
        self.assertTrue(scoring["missing_fields"])


if __name__ == "__main__":
    unittest.main()
