import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lead_service
from profiling_service import build_diagnosis, calculate_propensity


SAMPLE = {
    "full_name": "Laura Martínez",
    "id_type": "Cédula de ciudadanía",
    "id_number": "1012345678",
    "income_monthly": 3_000_000,
    "income_range": "Hasta 2 SMMLV",
    "affiliation_type": "Afiliado como trabajador",
    "affiliated": True,
    "negative_report": False,
    "purchase_horizon": "En los próximos 6 meses",
    "savings_range": "Más de $10 millones",
    "preferred_project": "Samán · VIS · Ricaurte",
    "bedrooms": 2,
    "source": "META_ADS",
    "campaign": "VIVIENDA_SAMAN_VIS",
}


class LeadServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(
            lead_service, "DB_PATH", Path(self.temp_dir.name) / "test_leads.db"
        )
        self.db_patch.start()
        lead_service.init_db()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_captures_and_scores_hot_lead(self):
        result = lead_service.capture_lead(SAMPLE, simulate_latency=0)
        self.assertEqual(result["lead_code"], "LEAD-00001")
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["rating"], "ALTA")
        self.assertEqual(result["crm_status"], "PROFILE_PENDING")

    def test_syncs_to_salesforce_only_after_vivi_profile(self):
        result = lead_service.capture_lead(SAMPLE, simulate_latency=0)
        profile = {
            "profile_complete": True,
            "project_origin": SAMPLE["preferred_project"],
            "interest_origin_project": True,
            "alternative_interest": None,
            "purchase_purpose": "Vivir con mi familia",
            "lives_in": "Suba",
            "works_in": "Calle 80",
            "household_size": 4,
            "housing_dream": "Balcón y zonas verdes",
            "desired_features": ["Balcón", "zonas verdes"],
            "purchase_horizon": SAMPLE["purchase_horizon"],
            "household_income": SAMPLE["income_monthly"],
            "savings_range": SAMPLE["savings_range"],
            "max_monthly_payment": 1_200_000,
            "affiliation_type": SAMPLE["affiliation_type"],
            "accepts_advisor_contact": True,
            "accepts_appointment": True,
        }
        scoring = calculate_propensity(profile)
        diagnosis = build_diagnosis(profile, scoring)
        status = lead_service.save_conversation_profile(
            result["lead_code"], profile, scoring, diagnosis
        )

        self.assertEqual(status, "SYNCED")
        stored = lead_service.list_leads()[0]
        self.assertEqual(stored["crm_status"], "SYNCED")
        self.assertEqual(stored["propensity_score"], scoring["propensity_score"])

    def test_detects_normalized_duplicate(self):
        lead_service.capture_lead(SAMPLE, simulate_latency=0)
        duplicate = lead_service.capture_lead(
            {**SAMPLE, "full_name": "  laura   martinez "}, simulate_latency=0
        )
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["duplicate_of"], "LEAD-00001")

    def test_same_name_with_different_document_is_not_duplicate(self):
        lead_service.capture_lead(SAMPLE, simulate_latency=0)
        second = lead_service.capture_lead(
            {**SAMPLE, "id_number": "1099999999"}, simulate_latency=0
        )
        self.assertFalse(second["duplicate"])

    def test_retry_does_not_sync_an_incomplete_profile(self):
        lead_service.capture_lead(SAMPLE, simulate_latency=0)
        self.assertEqual(lead_service.retry_crm_sync(), 0)
        self.assertEqual(
            lead_service.list_leads()[0]["crm_status"],
            "PROFILE_PENDING",
        )

    def test_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            lead_service.capture_lead({**SAMPLE, "full_name": "  "}, simulate_latency=0)


if __name__ == "__main__":
    unittest.main()
