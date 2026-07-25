import unittest

from campaign_service import build_attribution
from finance_service import SMMLV_2026, calculate_financial_profile


class CampaignAndFinanceTests(unittest.TestCase):
    def test_each_project_has_stable_distinct_campaign_identity(self):
        saman = build_attribution("Samán", "Instagram")
        araucaria = build_attribution("Araucaria", "Instagram")
        repeated = build_attribution("Samán", "Instagram")

        self.assertEqual(saman, repeated)
        self.assertNotEqual(saman["campaign_id"], araucaria["campaign_id"])
        self.assertEqual(saman["utm_source"], "instagram")

    def test_subsidy_under_two_smmlv_is_deterministic(self):
        profile = calculate_financial_profile(
            2 * SMMLV_2026 - 1,
            "Afiliado como trabajador",
        )

        self.assertEqual(profile["colsubsidio_subsidy"], 30 * SMMLV_2026)
        self.assertEqual(profile["concurrent_potential"], 20 * SMMLV_2026)
        self.assertEqual(profile["max_monthly_payment"], round((2 * SMMLV_2026 - 1) * 0.4))

    def test_non_affiliate_is_routed_without_subsidy(self):
        profile = calculate_financial_profile(2_000_000, "No afiliado")
        self.assertEqual(profile["colsubsidio_subsidy"], 0)
        self.assertFalse(profile["eligible_by_income"])


if __name__ == "__main__":
    unittest.main()
