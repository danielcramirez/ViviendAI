import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import lead_service


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
        self.assertEqual(result["crm_status"], "SYNCED")

    def test_detects_normalized_duplicate(self):
        lead_service.capture_lead(SAMPLE, simulate_latency=0)
        duplicate = lead_service.capture_lead(
            {**SAMPLE, "full_name": "  laura   martinez "}, simulate_latency=0
        )
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(duplicate["duplicate_of"], "LEAD-00001")

    def test_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            lead_service.capture_lead({**SAMPLE, "full_name": "  "}, simulate_latency=0)


if __name__ == "__main__":
    unittest.main()
