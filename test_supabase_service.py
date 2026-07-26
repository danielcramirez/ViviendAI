from __future__ import annotations

import json
import os
import unittest
from unittest.mock import MagicMock, patch

import supabase_service


class SupabaseServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            os.environ,
            {
                "DATA_BACKEND": "supabase",
                "SUPABASE_URL": "https://demo.supabase.co",
                "SUPABASE_SECRET_KEY": "sb_secret_test_only",
            },
            clear=False,
        )
        self.environment.start()

    def tearDown(self) -> None:
        self.environment.stop()

    def test_backend_is_enabled_only_with_valid_secret(self) -> None:
        self.assertTrue(supabase_service.is_configured())
        self.assertTrue(supabase_service.use_supabase())
        with patch.dict(
            os.environ,
            {"SUPABASE_SECRET_KEY": "ROTAR_EN_SUPABASE_Y_REEMPLAZAR_LOCALMENTE"},
        ):
            self.assertFalse(supabase_service.is_configured())
            self.assertFalse(supabase_service.use_supabase())

    @patch("supabase_service.urlopen")
    def test_upsert_uses_rest_api_and_never_exposes_local_id(self, mocked: MagicMock) -> None:
        response = MagicMock()
        response.read.return_value = b""
        mocked.return_value.__enter__.return_value = response

        supabase_service.upsert_lead(
            {
                "id": 7,
                "lead_code": "LEAD-00007",
                "full_name": "Daniel",
                "affiliated": 1,
                "crm_payload": '{"LeadSource": "Meta Ads"}',
            }
        )

        request = mocked.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertNotIn("id", body)
        self.assertTrue(body["affiliated"])
        self.assertEqual(body["crm_payload"]["LeadSource"], "Meta Ads")
        self.assertIn("/rest/v1/vivi_leads?", request.full_url)
        self.assertEqual(request.headers["Authorization"], "Bearer sb_secret_test_only")

    @patch("supabase_service.urlopen")
    def test_patch_filters_by_lead_code(self, mocked: MagicMock) -> None:
        response = MagicMock()
        response.read.return_value = b""
        mocked.return_value.__enter__.return_value = response

        supabase_service.patch_lead(
            "LEAD-00011",
            {"propensity_score": 90, "conversation_profile_json": {"dream": "balcón"}},
        )

        request = mocked.call_args.args[0]
        self.assertEqual(request.method, "PATCH")
        self.assertIn("lead_code=eq.LEAD-00011", request.full_url)


if __name__ == "__main__":
    unittest.main()
