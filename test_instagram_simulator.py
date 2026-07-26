import unittest

from instagram_simulator import empty_profile, process_message, start_conversation


class InstagramSimulatorTests(unittest.TestCase):
    def test_starts_with_person_and_campaign_project(self):
        messages = start_conversation("Laura Martínez", "Samán")
        self.assertIn("Laura", messages[0]["content"])
        self.assertIn("Samán", messages[0]["content"])

    def test_builds_structured_profile_and_score(self):
        profile = empty_profile("Samán", "CMP-SAMAN", "META-001")
        _, profile = process_message("Sí, me interesa", profile)
        _, profile = process_message("Para vivir con mi familia", profile)
        _, profile = process_message("Vivo en Suba", profile)
        _, profile = process_message("Trabajo en Chapinero", profile)
        _, profile = process_message("Somos 4 personas", profile)
        _, profile = process_message("Quiero balcón para mi perro", profile)
        _, profile = process_message("Sí, quiero que me contacten", profile)

        self.assertTrue(profile["interest_origin_project"])
        self.assertEqual(profile["lives_in"], "Vivo en Suba")
        self.assertEqual(profile["works_in"], "Trabajo en Chapinero")
        self.assertTrue(profile["profile_complete"])
        self.assertTrue(profile["accepts_advisor_contact"])

    def test_words_containing_si_or_no_do_not_change_intent(self):
        profile = empty_profile("Samán", "CMP-SAMAN", "LEAD-00001")
        _, profile = process_message("Sin problema, me interesa", profile)
        self.assertTrue(profile["interest_origin_project"])


if __name__ == "__main__":
    unittest.main()
